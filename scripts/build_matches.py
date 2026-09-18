#!/usr/bin/env python3
"""Bygg data/matches.json frå redaksjonelt stadfesta kampfakta.

Scriptet hentar ikkje automatisk frå fotball.no. Det validerer kampane i
`data/nff-import.json` og slepper berre gjennom kampar som oppfyller dei
redaksjonelle minimumskrava våre. Rikare kampdata blir vidareført når dei
faktisk er registrerte i kjelda.
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


def minute_value(value, match_number: str):
    if value in (None, ""):
        return None
    try:
        minute = int(value)
    except (TypeError, ValueError):
        fail(f"Ugyldig minutt i kamp {match_number}")
    if minute < 0 or minute > 150:
        fail(f"Ugyldig minutt i kamp {match_number}")
    return minute


def clean_events(events, match_number: str):
    allowed = {"goal", "substitution", "yellow_card", "red_card"}
    cleaned = []
    for event in events or []:
        event_type = event.get("type")
        if event_type not in allowed:
            continue
        team = event.get("team")
        if team not in {"home", "away"}:
            fail(f"Ugyldig event-lag i kamp {match_number}")
        item = {
            "minute": minute_value(event.get("minute"), match_number),
            "type": event_type,
            "team": team,
        }
        if event_type == "goal":
            player = str(event.get("player") or "").strip()
            if not player:
                fail(f"Mål utan spelar i kamp {match_number}")
            item["player"] = player
            if event.get("assist"):
                item["assist"] = str(event["assist"]).strip()
        elif event_type == "substitution":
            player_in = str(event.get("playerIn") or "").strip()
            player_out = str(event.get("playerOut") or "").strip()
            if not player_in and not player_out:
                fail(f"Spelarbyte utan spelarar i kamp {match_number}")
            item["playerIn"] = player_in or None
            item["playerOut"] = player_out or None
        else:
            player = str(event.get("player") or "").strip()
            if not player:
                fail(f"Kort utan spelar i kamp {match_number}")
            item["player"] = player
        cleaned.append(item)
    return cleaned


def clean_player(player):
    if not isinstance(player, dict):
        return None
    name = str(player.get("name") or "").strip()
    if not name:
        return None
    result = {"name": name}
    if player.get("number") not in (None, ""):
        result["number"] = player["number"]
    if player.get("position"):
        result["position"] = str(player["position"])
    return result


def clean_lineup(lineup):
    if not isinstance(lineup, dict):
        return None
    starters = [p for p in (clean_player(x) for x in lineup.get("starters", [])) if p]
    bench = [p for p in (clean_player(x) for x in lineup.get("bench", [])) if p]
    if not starters and not bench:
        return None
    result = {"starters": starters, "bench": bench}
    if lineup.get("formation"):
        result["formation"] = str(lineup["formation"])
    return result


def clean_lineups(lineups):
    if not isinstance(lineups, dict):
        return None
    home = clean_lineup(lineups.get("home"))
    away = clean_lineup(lineups.get("away"))
    if not home and not away:
        return None
    return {"home": home, "away": away}


def validate_match(raw: dict, cfg: dict) -> dict:
    required = ["matchNumber", "sourceUrl", "date", "age", "competition", "home", "away", "homeScore", "awayScore"]
    missing = [key for key in required if raw.get(key) in (None, "")]
    if missing:
        fail(f"Kamp manglar felt: {', '.join(missing)}")

    match_number = str(raw["matchNumber"]).strip()
    if not re.fullmatch(r"\d{8,14}", match_number):
        fail(f"Ugyldig kampnummer: {match_number}")

    fiks_id = str(raw.get("fiksId") or "").strip()
    if fiks_id and not re.fullmatch(r"\d+", fiks_id):
        fail(f"Ugyldig fiksId: {fiks_id}")

    source_url = str(raw["sourceUrl"]).strip()
    parsed = urlparse(source_url)
    host = (parsed.hostname or "").lower()
    if host not in {"fotball.no", "www.fotball.no"}:
        fail(f"Hovudkjelda må vere fotball.no for kamp {match_number}")
    if not parsed.path.startswith("/fotballdata/"):
        fail(f"Kjelda må vere ei offisiell fotballdata-side for kamp {match_number}")

    try:
        datetime.strptime(str(raw["date"]), "%Y-%m-%d")
    except ValueError:
        fail(f"Ugyldig dato for kamp {match_number}")

    age = str(raw["age"]).upper().replace(" ", "")
    age_match = re.fullmatch(r"([GJ])(\d{2})", age)
    senior = age in {"MENN", "KVINNER", "SENIOR"}
    if not age_match and not senior:
        fail(f"Ugyldig aldersklasse '{age}' for kamp {match_number}")
    if age_match and int(age_match.group(2)) < int(cfg.get("minimumAge", 13)):
        fail(f"Kamp {match_number} er yngre enn minimumsalder")

    try:
        home_score = int(raw["homeScore"])
        away_score = int(raw["awayScore"])
    except (TypeError, ValueError):
        fail(f"Sluttresultat manglar eller er ugyldig for kamp {match_number}")

    aliases = []
    for club in cfg["clubs"]:
        aliases.extend([club["name"], *club.get("aliases", [])])
    side = local_side(str(raw["home"]), str(raw["away"]), aliases)
    if not side:
        fail(f"Ingen godkjend lokal klubb funnen i kamp {match_number}")

    identity = fiks_id or match_number
    out = {
        "id": f"nff-{identity}",
        "fiksId": fiks_id or None,
        "matchNumber": match_number,
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
        "quality": "confirmed",
        "events": clean_events(raw.get("events"), match_number),
        "summary": raw.get("summary"),
        "nextMatch": raw.get("nextMatch"),
        "source": "NFF/fotball.no",
    }

    for field in ("competitionId", "referee", "attendance", "officials"):
        if raw.get(field) not in (None, ""):
            out[field] = raw[field]

    lineups = clean_lineups(raw.get("lineups"))
    if lineups:
        out["lineups"] = lineups

    return out


def main() -> int:
    cfg = load(CONFIG)
    payload = load(SOURCE)
    raw_matches = payload.get("matches", [])
    if not raw_matches:
        print("Ingen stadfesta kampar i data/nff-import.json. Beheld eksisterande nettsidedata.")
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
    print(f"Publiserer {len(matches)} stadfesta kampar.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FEIL: {exc}", file=sys.stderr)
        raise
