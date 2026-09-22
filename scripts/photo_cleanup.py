#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
PHOTOS_PATH = ROOT / "data" / "photos.json"
FORM_ID = "aQRDJ9"
API_BASE = "https://api.tally.so"


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def submission_exists(session, submission_id: str):
    url = f"{API_BASE}/forms/{FORM_ID}/submissions/{submission_id}"
    response = session.get(url, timeout=20)
    if response.status_code == 404:
        return False
    response.raise_for_status()
    return True


def main():
    api_key = os.environ.get("TALLY_API_KEY")
    if not api_key:
        print("TALLY_API_KEY missing; nothing cleaned.")
        return 0

    doc = load_json(PHOTOS_PATH, {"photos": {}})
    photos = doc.get("photos", {})
    if not photos:
        print("No published photos to check.")
        return 0

    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "tally-version": "2025-02-01",
    })

    status = {}
    removed = 0

    for match_number in list(photos.keys()):
        kept = []
        for item in photos.get(match_number, []):
            submission_id = str(item.get("submissionId") or "").strip()
            if not submission_id:
                kept.append(item)
                continue

            if submission_id not in status:
                try:
                    status[submission_id] = submission_exists(session, submission_id)
                except requests.RequestException as exc:
                    print(f"Could not verify submission {submission_id}: {exc}")
                    status[submission_id] = None

            exists = status[submission_id]
            if exists is False:
                removed += 1
                continue
            kept.append(item)

        if kept:
            photos[match_number] = kept
        else:
            photos.pop(match_number, None)

    if removed:
        save_json(PHOTOS_PATH, doc)
    print(f"Checked {len(status)} submission(s); removed {removed} photo record(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
