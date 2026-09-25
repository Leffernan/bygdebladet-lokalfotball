#!/usr/bin/env python3
"""Reparse every completed youth match from its official match page.

Used after parser changes to ensure historical match timelines are brought up to
the same standard as new matches. Requests are serial and deliberately paced.
"""
from __future__ import annotations

import argparse
import json
import time
from copy import deepcopy
from pathlib import Path

import requests

from detail_parser import parse_detail
from detail_corrections import apply_corrections, reconcile_goal_totals

ROOT = Path(__file__).resolve().parents[1]
MATCHES_PATH = ROOT / "data" / "matches.json"
STATE_PATH = ROOT / "data" / "engine-state.json"
CORRECTIONS_PATH = ROOT / "config" / "detail-corrections.json"
AUDIT_PATH = ROOT / "data" / "detail-audit.json"

UA = "Bygdebladet-Lokalfotball/1.0 (editorial match-data audit)"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def goals(events):
    return [
        {
            "minute": e.get("minute"),
            "team": e.get("team"),
            "label": e.get("label"),
            "player": e.get("player"),
            "ownGoal": bool(e.get("ownGoal")),
            "playerTeam": e.get("playerTeam"),
            "personUnavailable": bool(e.get("personUnavailable")),
        }
        for e in (events or []) if e.get("type") == "goal"
    ]


def validate_goal_totals(match, detail):
    found = {"home": 0, "away": 0}
    for event in detail.get("events") or []:
        if event.get("type") == "goal" and event.get("team") in found:
            found[event["team"]] += 1
    expected = {"home": int(match["homeScore"]), "away": int(match["awayScore"])}
    return found == expected, found, expected


def merge_detail(match, parsed):
    fields = ("events", "officials", "referee", "halfTime", "lineups", "attendance",
              "hasRegisteredEvents", "hasPublishedSquad")
    for field in fields:
        if field in parsed:
            match[field] = deepcopy(parsed[field])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=0.45)
    args = ap.parse_args()

    matches_doc = load(MATCHES_PATH)
    state_doc = load(STATE_PATH)
    corrections = load(CORRECTIONS_PATH)

    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"})

    audit = {
        "version": 2,
        "checked": 0,
        "changed": 0,
        "completeGoalTimelines": 0,
        "incompleteGoalTimelines": 0,
        "fetchErrors": [],
        "changes": [],
    }

    for index, match in enumerate(matches_doc.get("matches", []), start=1):
        if not isinstance(match.get("homeScore"), int) or not isinstance(match.get("awayScore"), int):
            continue
        url = match.get("sourceUrl")
        if not url or "fotball.no/fotballdata/kamp/" not in url:
            continue

        before = goals(match.get("events"))
        try:
            response = session.get(url, timeout=30)
            response.raise_for_status()
            parsed = parse_detail(response.text, match.get("home"), match.get("away"))
        except Exception as exc:
            audit["fetchErrors"].append({
                "matchNumber": str(match.get("matchNumber")),
                "home": match.get("home"),
                "away": match.get("away"),
                "error": str(exc)[:300],
            })
            continue

        merge_detail(match, parsed)
        key = str(match.get("matchNumber"))
        state = state_doc.get("matches", {}).get(key)
        if state is not None:
            state["detail"] = deepcopy(parsed)
            state["detailFetches"] = int(state.get("detailFetches") or 0) + 1

        after = goals(match.get("events"))
        audit["checked"] += 1
        if before != after:
            audit["changed"] += 1
            audit["changes"].append({
                "matchNumber": key,
                "home": match.get("home"),
                "away": match.get("away"),
                "score": f"{match.get('homeScore')}–{match.get('awayScore')}",
                "before": before,
                "after": after,
            })

        complete, found, expected = validate_goal_totals(match, parsed)
        if complete:
            audit["completeGoalTimelines"] += 1
        else:
            audit["incompleteGoalTimelines"] += 1

        print(f"[{index}] {key} {match.get('home')} – {match.get('away')}: "
              f"{'complete' if complete else 'incomplete'} {found}/{expected}")

        if args.delay > 0:
            time.sleep(args.delay)

    # First enforce the confirmed full-time score, then apply narrowly reviewed
    # corrections for documented parser edge cases.
    reconciliation_changes = reconcile_goal_totals(matches_doc, state_doc)
    correction_changes = apply_corrections(matches_doc, state_doc, corrections)
    audit["goalReconciliationRecordUpdates"] = reconciliation_changes
    audit["reviewedCorrectionRecordUpdates"] = correction_changes

    # Recalculate completeness after corrections for final published state.
    final_complete = final_incomplete = 0
    for match in matches_doc.get("matches", []):
        if not isinstance(match.get("homeScore"), int) or not isinstance(match.get("awayScore"), int):
            continue
        ok, _, _ = validate_goal_totals(match, {"events": match.get("events") or []})
        if ok:
            final_complete += 1
        else:
            final_incomplete += 1
    audit["finalCompleteGoalTimelines"] = final_complete
    audit["finalIncompleteGoalTimelines"] = final_incomplete

    dump(MATCHES_PATH, matches_doc)
    dump(STATE_PATH, state_doc)
    dump(AUDIT_PATH, audit)
    print(json.dumps({k: v for k, v in audit.items() if k not in {"changes", "fetchErrors"}},
                     ensure_ascii=False))
    return 0 if not audit["fetchErrors"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
