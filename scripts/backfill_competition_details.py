#!/usr/bin/env python3
"""One-time, rate-limited detail backfill for an added youth competition."""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from detail_parser import parse_detail

ROOT = Path(__file__).resolve().parents[1]
MATCHES = ROOT / "data" / "matches.json"
STATE = ROOT / "data" / "engine-state.json"
SOURCES = ROOT / "config" / "sources.json"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def safe_goals(match, detail):
    if detail.get("structuredTimeline") is not True:
        return False
    goals = [e for e in detail.get("events") or [] if e.get("type") == "goal"]
    totals = Counter(e.get("team") for e in goals)
    if (totals["home"], totals["away"]) != (match["homeScore"], match["awayScore"]):
        return False
    for goal in goals:
        minute = goal.get("minute")
        if type(minute) is not int or minute < 1 or minute > 150:
            return False
        if goal.get("ownGoal") and goal.get("playerTeam") != (
            "away" if goal.get("team") == "home" else "home"
        ):
            return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--competition-key", default="j13-7er-host")
    args = ap.parse_args()

    matches_doc, state_doc, sources = load(MATCHES), load(STATE), load(SOURCES)
    candidates = [m for m in matches_doc.get("matches", [])
                  if m.get("competitionId") == args.competition_key
                  and type(m.get("homeScore")) is int
                  and type(m.get("awayScore")) is int]
    if not candidates:
        raise SystemExit("No completed matches in requested competition")

    session = requests.Session()
    session.headers.update(sources.get("headers") or {})
    delay = max(1.5, float(sources.get("minimumDelaySeconds") or 1.5))
    updated = verified = unverified = 0
    errors = []

    for i, match in enumerate(candidates):
        key = str(match["matchNumber"])
        state = state_doc.get("matches", {}).get(key)
        if not state:
            errors.append(f"{key}: state record missing")
            continue
        if state.get("detailFetches") and state.get("detail") is not None:
            continue

        url = match.get("sourceUrl")
        if not url or not url.startswith("https://www.fotball.no/fotballdata/kamp/?fiksId="):
            errors.append(f"{key}: invalid source URL")
            continue
        try:
            response = session.get(url, timeout=float(sources.get("timeoutSeconds") or 20))
            response.raise_for_status()
            parsed = parse_detail(response.text, match["home"], match["away"])
        except Exception as exc:
            errors.append(f"{key}: {type(exc).__name__}: {str(exc)[:90]}")
            continue

        trusted = safe_goals(match, parsed)
        if not trusted:
            # Keep factual match score, but never put a contradictory or
            # incomplete goal sequence into either timeline or editorial prose.
            parsed["events"] = []
            parsed["structuredTimeline"] = False
            unverified += 1
        else:
            verified += 1
        fields = ("events", "officials", "referee", "halfTime", "lineups", "attendance")
        for field in fields:
            if field in parsed:
                match[field] = deepcopy(parsed[field])
        match["goalTimelineVerified"] = trusted
        state["detail"] = deepcopy(parsed)
        state["goalTimelineVerified"] = trusted
        state["detailFetches"] = int(state.get("detailFetches") or 0) + 1
        state["detailFetchedAt"] = datetime.now(ZoneInfo("Europe/Oslo")).isoformat(timespec="seconds")
        updated += 1
        print(f"{key}: {'complete verified timeline' if trusted else 'result only (details not reliable)'}")
        if i + 1 < len(candidates):
            time.sleep(delay)

    save(MATCHES, matches_doc)
    save(STATE, state_doc)
    print(f"Backfill {args.competition_key}: {updated} checked, {verified} verified, "
          f"{unverified} result only, {len(errors)} errors")
    for err in errors:
        print(err)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
