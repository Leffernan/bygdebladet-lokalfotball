#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import unicodedata
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
MATCHES_PATH = ROOT / "data" / "matches.json"
PHOTOS_PATH = ROOT / "data" / "photos.json"
FORM_ID = "aQRDJ9"
API_BASE = "https://api.tally.so"

LABEL_MATCH = "Kva kamp gjeld bildet?"
LABEL_DATE = "Dato for kampen"
LABEL_PHOTOGRAPHER = "Kven har tatt bildet?"
LABEL_FILE = "Last opp bilde"
LABEL_CAPTION = "Bildetekst / kven er på bildet?"
LABEL_RIGHTS = "Rett til publisering"


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def norm(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold().replace("ø", "o").replace("æ", "ae").replace("å", "a")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def fetch_submission(api_key, submission_id):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "tally-version": "2025-02-01",
    }
    url = f"{API_BASE}/forms/{FORM_ID}/submissions/{submission_id}"
    response = requests.get(url, headers=headers, timeout=25)
    response.raise_for_status()
    return response.json()


def question_labels(doc):
    labels = {}
    field_labels = {}
    for q in doc.get("questions", []):
        qid = str(q.get("id") or "")
        title = q.get("title") or q.get("label")
        if qid and title:
            labels[qid] = str(title)
        for f in q.get("fields", []) or []:
            title = f.get("title")
            uuid = f.get("uuid")
            if uuid and title:
                field_labels[str(uuid)] = str(title)
    return labels, field_labels


def flatten_answers(doc):
    submission = doc.get("submission") or {}
    labels, field_labels = question_labels(doc)
    result = {}
    raw = []

    for response in submission.get("responses", []) or []:
        qid = str(response.get("questionId") or "")
        label = labels.get(qid, qid)
        answer = response.get("answer")
        raw.append((label, answer))

        if isinstance(answer, dict):
            for key, value in answer.items():
                result[str(key)] = value
        else:
            result[label] = answer

        # Hidden-field payloads can be arrays/objects depending on API version.
        if isinstance(answer, list):
            for item in answer:
                if isinstance(item, dict) and "name" in item and "value" in item:
                    result[str(item["name"])] = item["value"]

    return result, raw


def answer_by_label(flat, label, default=None):
    if label in flat:
        return flat[label]
    target = norm(label)
    for key, value in flat.items():
        if norm(key) == target:
            return value
    return default


def resolve_match(matches, flat, override=None):
    if override:
        for match in matches:
            if str(match.get("matchNumber")) == str(override) or match.get("id") == override:
                return match
        raise SystemExit(f"Unknown match number: {override}")

    hidden = flat.get("matchNumber")
    if hidden:
        for match in matches:
            if str(match.get("matchNumber")) == str(hidden):
                return match

    date_value = answer_by_label(flat, LABEL_DATE) or flat.get("matchDate")
    query = answer_by_label(flat, LABEL_MATCH, "")
    if not date_value:
        raise SystemExit("Submission has no match date and no matchNumber.")

    day = str(date_value)[:10]
    candidates = [m for m in matches if str(m.get("date")) == day]
    if not candidates:
        raise SystemExit(f"No match found for date {day}.")

    if len(candidates) == 1:
        return candidates[0]

    q = norm(query)
    if not q:
        raise SystemExit(f"Several matches found for {day}; supply match_number override.")

    scored = []
    for match in candidates:
        words = set(norm(f"{match.get('home','')} {match.get('away','')}").split())
        query_words = set(q.split())
        score = len(words & query_words)
        if norm(match.get("home")) in q or norm(match.get("away")) in q:
            score += 4
        scored.append((score, match))

    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored or scored[0][0] <= 0:
        raise SystemExit(f"Could not match submission to a game on {day}.")
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        raise SystemExit(f"Ambiguous match on {day}; supply match_number override.")
    return scored[0][1]


def file_items(value):
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            value = parsed
        except Exception:
            if value.startswith("http"):
                return [{"url": value, "name": "Kampbilde"}]
            return []

    if isinstance(value, dict):
        value = [value]

    out = []
    for item in value or []:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if not url:
            continue
        out.append({
            "id": item.get("id"),
            "name": item.get("name"),
            "url": url,
            "mimeType": item.get("mimeType"),
            "size": item.get("size"),
        })
    return out


def has_rights(value):
    if isinstance(value, list):
        value = " ".join(str(x) for x in value)
    return "stadfestar" in norm(value) and "publisering" in norm(value)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission-id", required=True)
    parser.add_argument("--match-number")
    args = parser.parse_args()

    api_key = os.environ.get("TALLY_API_KEY")
    if not api_key:
        raise SystemExit("TALLY_API_KEY is missing.")

    doc = fetch_submission(api_key, args.submission_id)
    submission = doc.get("submission") or {}
    if not submission.get("isCompleted", False):
        raise SystemExit("Submission is not completed.")

    flat, _ = flatten_answers(doc)
    rights = answer_by_label(flat, LABEL_RIGHTS)
    if rights is not None and not has_rights(rights):
        raise SystemExit("Publication rights confirmation is missing.")

    matches_doc = load_json(MATCHES_PATH, {"matches": []})
    match = resolve_match(matches_doc.get("matches", []), flat, args.match_number)
    match_number = str(match.get("matchNumber") or match.get("id"))

    files = file_items(answer_by_label(flat, LABEL_FILE))
    if not files:
        raise SystemExit("No uploaded images found in submission.")

    photographer = str(answer_by_label(flat, LABEL_PHOTOGRAPHER, "") or "").strip()
    caption = str(answer_by_label(flat, LABEL_CAPTION, "") or "").strip()

    photos_doc = load_json(PHOTOS_PATH, {"photos": {}})
    bucket = photos_doc.setdefault("photos", {}).setdefault(match_number, [])

    existing = {str(x.get("id")) for x in bucket}
    added = 0
    for i, file in enumerate(files, start=1):
        image_id = f"tally-{args.submission_id}-{file.get('id') or i}"
        if image_id in existing:
            continue
        bucket.append({
            "id": image_id,
            "submissionId": args.submission_id,
            "imageUrl": file["url"],
            "photographer": photographer or None,
            "caption": caption or None,
            "submittedAt": submission.get("submittedAt"),
            "approvedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
            "storage": "tally",
        })
        existing.add(image_id)
        added += 1

    save_json(PHOTOS_PATH, photos_doc)
    print(f"Matched {args.submission_id} -> {match_number}; published {added} image(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
