#!/usr/bin/env python3
"""Bygg data/matches.json fra NFF-verifiserte kampfakta.

Scriptet henter ikke automatisk fra fotball.no. Det validerer redaksjonelt
registrerte NFF-kamper i data/nff-import.json og slipper bare gjennom kamper
som oppfyller kilde- og kvalitetskravene våre.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "nff.json"
SOURCE = ROOT / "data" / "nff-import.json"
OUTPUT = ROOT / "data" / "matches.json"


def load(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def fail(msg: str) -> None:
    raise ValueError(msg)


def local_side(home: str, away: str, aliases: list[str]) -> str | None:
    h = home.casefold()
    a = away.casefold()
    home_local = any(x.casefold() in h for x in aliases)
    away_local = any(x.casefold() in a for x in aliases)
    if home_local and away_local:
        return "both"
    if home_local:
        return "home"
    if away_local:
        return "away"
    return None


def validate_match(raw: dict, cfg: dict) -> dict:
    required = ["fiksId", "sourceUrl", "date", "age", "competition", "home", "away", "homeScore", "awayScore"]
    missing = [key for key in required if raw.get(key) in (None, "")]
    if missing:
        fail(f"Kamp mangler felt: {', '.join(missing)}")

    fiks_id = str(raw["fiksId"]).strip()
    if not re.fullmatch(r"\d+", fiks_id):
        fail(f"Ugyldig fiksId: {fiks_id}")

    source_url = str(raw["sourceUrl"]).strip()
    host = (urlparse(source_url).hostname or "").lower()
    if host not in {"fotball.no", "www.fotball.no"}:
        fail(f"Kilde må være fotball.no for kamp {fiks_id}")

    try:
        datetime.strptime(str(raw["date"]), "%Y-%m-%d")
    except ValueError:
        fail(f"Ugyldig dato for kamp {fiks_id}")

    age = str(raw["age"]).upper().replace(" ", "")
    m = re.fullmatch(r"([GJ])(\d{2})", age)
    senior = age in {"MENN", "KVINNER", "SENIOR"}
    if not m and not senior:
        fail(f"Ugyldig aldersklasse '{age}' for kamp {fiks_id}")
    if m and int(m.group(2)) < int(cfg.get("minimumAge", 13)):
        fail(f"Kamp {fiks_id} er yngre enn minimumsalder")

    try:
        home_score = int(raw["homeScore"])
        away_score = int(raw["awayScore"])
    except (TypeError, ValueError):
        fail(f"Sluttresultat mangler/er ugyldig for kamp {fiks_id}")

    aliases = []
    for club in cfg["clubs"]:
        aliases.extend([club["name"], *club.get("aliases", [])])
    side = local_side(str(raw["home"]), str(raw["away"]), aliases)
    if not side:
        fail(f"Ingen godkjent lokal klubb funnet i kamp {fiks_id}")

    events = raw.get("events") or []
    clean_events = []
    for event in events:
        if event.get("type") != "goal":
            continue
        if event.get("team") not in {"home", "away"}:
            fail(f"Ugyldig event-lag i kamp {fiks_id}")
        player = str(event.get("player") or "").strip()
        if not player:
            fail(f"Mål uten spiller i kamp {fiks_id}")
        minute = event.get("minute")
        if minute not in (None, ""):
            try:
                minute = int(minute)
            except (TypeError, ValueError):
                fail(f"Ugyldig målminutt i kamp {fiks_id}")
        clean_events.append({"minute": minute, "type": "goal", "team": event["team"], "player": player})

    return {
        "id": f"nff-{fiks_id}",
        "fiksId": fiks_id,
        "sourceUrl": source_url,
        "date": str(raw["date"]),
        "time": str(raw.get("time") or ""),
        "age": age,
        "competition": str(raw["competition"]),
        "venue": raw.get("venue"),
        "home": str(raw["home"]),
        "away": str(raw["away"]),
        "homeScore": home_score,
        "awayScore": away_score,
        "halfTime": raw.get("halfTime"),
        "localTeam": side,
        "quality": "verified",
        "events": clean_events,
        "summary": raw.get("summary"),
        "nextMatch": raw.get("nextMatch"),
        "source": "NFF/fotball.no"
    }


def main() -> int:
    cfg = load(CONFIG)
    payload = load(SOURCE)
    raw_matches = payload.get("matches", [])
    if not raw_matches:
        print("Ingen NFF-verifiserte kamper i data/nff-import.json. Beholder eksisterende nettsidedata.")
        return 0

    matches = [validate_match(item, cfg) for item in raw_matches]
    matches.sort(key=lambda x: (x["date"], x.get("time") or ""), reverse=True)

    existing = load(OUTPUT) if OUTPUT.exists() else {}
    out = {
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "photoSubmitUrl": existing.get("photoSubmitUrl", "#"),
        "matches": matches,
    }
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Publiserer {len(matches)} NFF-verifiserte kamper.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FEIL: {exc}", file=sys.stderr)
        raise
