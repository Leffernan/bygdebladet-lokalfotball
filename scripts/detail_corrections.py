#!/usr/bin/env python3
"""Apply narrowly scoped, reviewed goal corrections after every NFF sync.

Only the goal list is replaced. Non-goal match details and timeline events remain
untouched. Exact match identity and score must agree before any correction is used.
"""
from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "detail-corrections.json"
MATCHES = ROOT / "data" / "matches.json"
STATE = ROOT / "data" / "engine-state.json"


def apply_corrections(matches_doc, state_doc, config_doc):
    changes = 0
    for key, correction in config_doc.get("matches", {}).items():
        goals = correction["events"]
        if not goals or any(event.get("type") != "goal" for event in goals):
            raise ValueError(f"{key}: corrections must contain goal events only")

        counts = Counter(event.get("team") for event in goals)
        if (counts["home"], counts["away"]) != (correction["homeScore"], correction["awayScore"]):
            raise ValueError(f"{key}: corrected goal counts conflict with the final score")
        if any(event.get("ownGoal") and event.get("playerTeam") !=
               ("away" if event.get("team") == "home" else "home") for event in goals):
            raise ValueError(f"{key}: own goal must benefit the opposite team")

        match = next((m for m in matches_doc.get("matches", [])
                      if str(m.get("matchNumber")) == str(key)), None)
        state = state_doc.get("matches", {}).get(str(key))
        if not match and not state:
            continue

        for record in (match, state):
            if record is None:
                continue
            for field in ("home", "away", "fiksId", "homeScore", "awayScore"):
                if str(record.get(field)) != str(correction.get(field)):
                    raise ValueError(f"{key}: {field} does not match; refusing to override")

            detail = record if record is match else record.setdefault("detail", {})
            before = detail.get("events") or []
            other = [e for e in before if e.get("type") != "goal"]
            new = sorted(other + deepcopy(goals), key=lambda e: e.get("minute") if
                         isinstance(e.get("minute"), int) else 999)
            if new != before:
                detail["events"] = new
                changes += 1
    return changes


def main():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    matches = json.loads(MATCHES.read_text(encoding="utf-8"))
    state = json.loads(STATE.read_text(encoding="utf-8"))
    count = apply_corrections(matches, state, config)
    if count:
        MATCHES.write_text(json.dumps(matches, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Reviewed goal correction record updates: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
