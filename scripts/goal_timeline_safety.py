#!/usr/bin/env python3
"""Keep source-sync from publishing contradictory or unverified goal timelines."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATCHES = ROOT / "data" / "matches.json"
STATE = ROOT / "data" / "engine-state.json"
AUDIT = ROOT / "data" / "detail-audit.json"
CORRECTIONS = ROOT / "config" / "detail-corrections.json"


def read(path, fallback):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else fallback


def safe(events, match):
    goals = [e for e in events if e.get("type") == "goal"]
    counts = Counter(e.get("team") for e in goals)
    if (counts["home"], counts["away"]) != (
        match.get("homeScore"), match.get("awayScore")
    ):
        return False
    for goal in goals:
        if type(goal.get("minute")) is not int or not 0 < goal["minute"] <= 150:
            return False
        if goal.get("ownGoal") and goal.get("playerTeam") != (
            "away" if goal.get("team") == "home" else "home"
        ):
            return False
    return True


def apply(matches_doc, state_doc, audit_doc, corrections_doc):
    statuses = audit_doc.get("matches", {})
    corrected = set(corrections_doc.get("matches", {}))
    changed = 0
    for match in matches_doc.get("matches", []):
        key = str(match.get("matchNumber"))
        state = state_doc.get("matches", {}).get(key)
        audit_status = statuses.get(key, {}).get("status")
        events = match.get("events") or []
        structured = bool((state or {}).get("detail", {}).get("structuredTimeline"))
        if audit_status == "needs_review":
            verified = False
        elif key in corrected or structured or audit_status in {"verified", "reviewed_correction"}:
            verified = safe(events, match)
        elif events:
            verified = False
        else:
            # No official goals available: do not infer a complete timeline.
            verified = False

        if match.get("goalTimelineVerified") is not verified:
            match["goalTimelineVerified"] = verified
            changed += 1
        if state is not None and state.get("goalTimelineVerified") is not verified:
            state["goalTimelineVerified"] = verified
            changed += 1
    return changed


def main():
    m = read(MATCHES, {"matches": []})
    s = read(STATE, {"matches": {}})
    a = read(AUDIT, {"matches": {}})
    c = read(CORRECTIONS, {"matches": {}})
    count = apply(m, s, a, c)
    if count:
        MATCHES.write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        STATE.write_text(json.dumps(s, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Goal timeline safety status updates: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
