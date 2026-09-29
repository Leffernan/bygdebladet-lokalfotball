#!/usr/bin/env python3
"""Publish scored local senior fixtures before the next NFF sync."""
import csv
import gzip
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
now = datetime.now(ZoneInfo("Europe/Oslo"))


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def save(name, value):
    (DATA / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    results = load("matches.json")
    upcoming = load("upcoming.json")
    existing = {m["matchNumber"]: m for m in results["matches"] if m.get("matchNumber")}
    future = {m["matchNumber"]: m for m in upcoming["matches"] if m.get("matchNumber")}
    with gzip.open(DATA / "fixture_schedule.csv.gz", "rt", encoding="utf-8", newline="") as fh:
        fixtures = list(csv.DictReader(fh))
    for r in fixtures:
        if r["age"] not in {"MENN", "KVINNER"} or not r["localTeam"]:
            continue
        number = r["matchNumber"]
        url = f"https://www.fotball.no/fotballdata/turnering/hjem/?fiksId={r['tournamentId']}"
        score = re.fullmatch(r"(\d+)-(\d+)", r["seedResult"])
        common = {k: r[k] for k in ("date", "time", "age", "competition", "home", "away", "matchNumber", "localTeam")}
        common.update(competitionId=r["competitionKey"], venue=r["venue"], sourceUrl=url)
        if score:
            existing[number] = {
                "id": f"match-{number}", "fiksId": None, **common,
                "homeScore": int(score[1]), "awayScore": int(score[2]),
                "halfTime": None, "events": [], "summary": None,
                "nextMatch": None, "source": "fotball.no",
            }
        elif datetime.fromisoformat(r["date"] + "T" + r["time"]).replace(tzinfo=now.tzinfo) >= now - timedelta(hours=2):
            future[number] = {k: v for k, v in common.items() if k != "localTeam"}
    results["matches"] = sorted(existing.values(), key=lambda m: (m["date"], m.get("time") or ""), reverse=True)
    upcoming["matches"] = sorted(future.values(), key=lambda m: (m["date"], m.get("time") or ""))
    results["generatedAt"] = upcoming["generatedAt"] = now.isoformat(timespec="seconds")
    save("matches.json", results)
    save("upcoming.json", upcoming)
    print(f"Published {len(results['matches'])} finished and {len(upcoming['matches'])} upcoming local matches")


if __name__ == "__main__":
    main()
