#!/usr/bin/env python3
"""One-pass, low-traffic audit of all published youth-match NFF timelines.

Uses each official match URL once, reads structured event rows and changes
published details only when the score and goal counts match. All uncertain
cases remain on a review list rather than receiving guessed event data.
"""
from __future__ import annotations

import json
import os
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from detail_parser import _lines, _page_score, parse_detail
from detail_corrections import apply_corrections

ROOT = Path(__file__).resolve().parents[1]
MATCHES = ROOT / "data" / "matches.json"
STATE = ROOT / "data" / "engine-state.json"
CORRECTIONS = ROOT / "config" / "detail-corrections.json"
AUDIT = ROOT / "data" / "detail-audit.json"
DELAY = float(os.getenv("NFF_AUDIT_DELAY_SECONDS", "1.6"))
REQUEST_TIMEOUT = 25


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def score_pair(record):
    return int(record["homeScore"]), int(record["awayScore"])


def goal_count(events):
    count = Counter(e.get("team") for e in events if e.get("type") == "goal")
    return (count["home"], count["away"])


def events_valid(events):
    for event in events:
        if event.get("type") != "goal":
            continue
        minute = event.get("minute")
        if type(minute) is not int or minute < 0 or minute > 150:
            return False
        if event.get("team") not in {"home", "away"}:
            return False
        if event.get("ownGoal") and event.get("playerTeam") != (
            "away" if event["team"] == "home" else "home"
        ):
            return False
    return True


def apply_verified(match, state, events):
    if match.get("events") != events:
        match["events"] = events
    match["goalTimelineVerified"] = True
    if state is not None:
        state.setdefault("detail", {})["events"] = events
        state["detail"]["structuredTimeline"] = True
        state["goalTimelineVerified"] = True


def review_flag(match, state):
    match["goalTimelineVerified"] = False
    if state is not None:
        state["goalTimelineVerified"] = False


def main():
    matches_doc = read(MATCHES)
    state_doc = read(STATE)
    corrections_doc = read(CORRECTIONS)
    existing = read(AUDIT) if AUDIT.exists() else {}
    records = {}
    summary = Counter()
    matches = [
        m for m in matches_doc.get("matches", [])
        if m.get("age", "")[:1] in {"G", "J"} and
        isinstance(m.get("homeScore"), int) and
        isinstance(m.get("awayScore"), int)
    ]
    # Each published match is checked only once in this audit run.
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/html",
    })
    print(f"Auditing {len(matches)} published youth matches", flush=True)

    for index, match in enumerate(matches):
        if index:
            time.sleep(DELAY)
        key = str(match["matchNumber"])
        state = state_doc.get("matches", {}).get(key)
        entry = {
            "matchNumber": key,
            "date": match.get("date"),
            "home": match.get("home"),
            "away": match.get("away"),
            "finalScore": f"{match['homeScore']}–{match['awayScore']}",
            "sourceUrl": match.get("sourceUrl"),
        }
        source = str(match.get("sourceUrl") or "")
        parsed_url = urlparse(source)
        if parsed_url.hostname not in {"www.fotball.no", "fotball.no"} or "/fotballdata/kamp/" not in parsed_url.path:
            entry.update(status="needs_review", reason="Unrecognized official source URL")
            review_flag(match, state)
        else:
            try:
                response = session.get(source, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
                raw = _lines(soup)
                official_score = _page_score(raw, match["home"], match["away"])
                parsed = parse_detail(response.text, home=match["home"], away=match["away"])
                events = parsed["events"]
                counts = goal_count(events)
                entry["officialGoalCount"] = f"{counts[0]}–{counts[1]}"
                entry["structuredTimeline"] = bool(parsed.get("structuredTimeline"))
                entry["ownGoals"] = [
                    {"minute": e.get("minute"), "team": e.get("team"), "playerTeam": e.get("playerTeam")}
                    for e in events if e.get("ownGoal")
                ]

                if official_score != score_pair(match):
                    entry.update(status="needs_review", reason="Official score not confirmed against stored final score")
                    review_flag(match, state)
                elif parsed.get("structuredTimeline") and counts == score_pair(match) and events_valid(events):
                    apply_verified(match, state, events)
                    entry.update(status="verified", reason="Structured event rows match official final score")
                elif not parsed.get("structuredTimeline") and not any(e.get("type") == "goal" for e in events):
                    entry.update(status="no_goal_data", reason="No structured goal timeline on official page")
                    # Keep only known match facts; do not publish unverified legacy goal sequence.
                    if any(e.get("type") == "goal" for e in (match.get("events") or [])):
                        review_flag(match, state)
                    elif match.get("goalTimelineVerified") is not True:
                        match["goalTimelineVerified"] = False
                else:
                    entry.update(status="needs_review", reason="Official event tally or timeline structure could not be verified")
                    review_flag(match, state)

            except (requests.RequestException, ValueError) as exc:
                entry.update(status="source_unavailable", reason=type(exc).__name__)
                # A transient source error must not discard previously verified facts.

        records[key] = entry
        summary[entry["status"]] += 1
        print(f"{index+1}/{len(matches)} {key}: {entry['status']}" +
              (f" ({entry.get('officialGoalCount')})" if entry.get("officialGoalCount") else ""),
              flush=True)

    # Preserve the two explicitly reviewed goal sequences after the automatic
    # pass; they have verified match identity, result, minute and goal type.
    applied = apply_corrections(matches_doc, state_doc, corrections_doc)
    for key in corrections_doc.get("matches", {}):
        if key in records:
            m = next((m for m in matches if str(m["matchNumber"]) == key), None)
            if m and goal_count(m.get("events") or []) == score_pair(m):
                m["goalTimelineVerified"] = True
                state = state_doc.get("matches", {}).get(key)
                if state:
                    state["goalTimelineVerified"] = True
                summary[records[key]["status"]] -= 1
                records[key]["status"] = "reviewed_correction"
                records[key]["reason"] = "Reviewed goal sequence supersedes ambiguous extraction"
                summary["reviewed_correction"] += 1

    write(MATCHES, matches_doc)
    write(STATE, state_doc)
    audit_doc = {
        "auditedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "totalMatches": len(matches),
        "sourceRequests": len(matches),
        "reviewedCorrectionUpdates": applied,
        "summary": {name: count for name, count in sorted(summary.items()) if count},
        "matches": records,
    }
    write(AUDIT, audit_doc)
    print("FINAL_AUDIT", json.dumps(audit_doc["summary"], ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
