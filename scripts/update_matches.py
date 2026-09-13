#!/usr/bin/env python3
"""Oppdater data/matches.json fra Fotballdata.

Dette er en forsiktig adapter rundt det dokumenterte Fotballdata-API-et.
Den publiserer aldri et tomt resultat og krever eksplisitte klubb-ID-er og
API-legitimasjon. Event-/målscorer-normalisering er laget defensivt fordi
feltstrukturen må verifiseres mot vår egen tilgang før produksjon.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "fotballdata.json"
OUTPUT_PATH = ROOT / "data" / "matches.json"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def api_get(base_url: str, path: str, cid: str, cwd: str, **params: Any) -> Any:
    query = {"cid": cid, "cwd": cwd, "format": "json", **params}
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}?{urllib.parse.urlencode(query)}"
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "Bygdebladet-Lokalfotball/0.1"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def collection(payload: Any, *keys: str) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if not isinstance(payload, dict):
        return []
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]
    # ServiceStack-svar kan ha ett ekstra wrapper-nivå.
    for value in payload.values():
        if isinstance(value, dict):
            found = collection(value, *keys)
            if found:
                return found
    return []


def first(record: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return None


def nested_name(value: Any) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        result = first(value, "Name", "TeamName", "StadiumName", "TournamentName", "FullName")
        return str(result).strip() if result else None
    return None


def int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        match = re.search(r"-?\d+", str(value))
        return int(match.group()) if match else None


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value)
    dotnet = re.search(r"/Date\((\d+)", text)
    if dotnet:
        return datetime.fromtimestamp(int(dotnet.group(1)) / 1000, tz=timezone.utc).astimezone()
    text = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.astimezone()
        return dt
    except ValueError:
        return None


def detect_age(*texts: str | None) -> str | None:
    for text in texts:
        if not text:
            continue
        m = re.search(r"\b([GJ])\s*-?\s*(\d{2})\b", text, flags=re.IGNORECASE)
        if m:
            return f"{m.group(1).upper()}{m.group(2)}"
    return None


def contains_alias(name: str, aliases: list[str]) -> bool:
    folded = name.casefold()
    return any(alias.casefold() in folded for alias in aliases)


def normalize_match(raw: dict[str, Any], aliases: list[str], minimum_age: int) -> dict[str, Any] | None:
    match_id = first(raw, "MatchId", "Id", "matchId", "id")
    home = first(raw, "HomeTeamName", "HomeName", "HomeTeamNameInTournament") or nested_name(raw.get("HomeTeam"))
    away = first(raw, "AwayTeamName", "GuestTeamName", "AwayName", "AwayTeamNameInTournament") or nested_name(raw.get("AwayTeam")) or nested_name(raw.get("GuestTeam"))
    if not match_id or not home or not away:
        return None

    home = str(home).strip()
    away = str(away).strip()
    local_home = contains_alias(home, aliases)
    local_away = contains_alias(away, aliases)
    if not (local_home or local_away):
        return None

    home_score = int_or_none(first(raw, "HomeGoals", "HomeScore", "NoHomeGoals", "HomeTeamGoals", "HomeTeamScore"))
    away_score = int_or_none(first(raw, "AwayGoals", "AwayScore", "NoAwayGoals", "GuestGoals", "AwayTeamGoals", "AwayTeamScore"))
    # Hovedregelen vår: aldri publiser kamp uten registrert sluttresultat.
    if home_score is None or away_score is None:
        return None

    competition = first(raw, "TournamentName", "CompetitionName") or nested_name(raw.get("Tournament"))
    age = detect_age(str(competition or ""), home, away)
    if not age:
        # Ikke gjett aldersklasse eller seniornivå.
        return None
    age_number = int(re.search(r"\d+", age).group())
    if age_number < minimum_age:
        return None

    dt = parse_datetime(first(raw, "MatchDate", "StartDate", "Date", "Kickoff"))
    if not dt:
        return None

    venue = first(raw, "StadiumName", "VenueName") or nested_name(raw.get("Stadium"))
    half_time = first(raw, "HalfTimeResult", "HalfTimeScore", "ResultHalfTime")

    return {
        "id": str(match_id),
        "date": dt.date().isoformat(),
        "time": dt.strftime("%H:%M"),
        "age": age,
        "competition": str(competition or age),
        "venue": str(venue) if venue else None,
        "home": home,
        "away": away,
        "homeScore": home_score,
        "awayScore": away_score,
        "halfTime": str(half_time) if half_time else None,
        "localTeam": "home" if local_home and not local_away else "away" if local_away and not local_home else "both",
        "quality": "result",
        "events": [],
        "summary": None,
        "nextMatch": None,
        "source": "Fotballdata/FIKS",
    }


def main() -> int:
    config = load_json(CONFIG_PATH)
    cid = os.environ.get("FOTBALLDATA_CID", "").strip()
    cwd = os.environ.get("FOTBALLDATA_CWD", "").strip()

    if not cid or not cwd:
        print("Fotballdata er ikkje konfigurert: manglar FOTBALLDATA_CID/FOTBALLDATA_CWD. Hoppar over.")
        return 0

    configured_clubs = [club for club in config["clubs"] if club.get("clubId")]
    if not configured_clubs:
        print("Ingen clubId er lagt inn i config/fotballdata.json. Hoppar over utan å endre data.")
        return 0

    base_url = config["baseUrl"]
    minimum_age = int(config.get("minimumAge", 13))
    matches_by_id: dict[str, dict[str, Any]] = {}

    for club in configured_clubs:
        club_id = str(club["clubId"])
        aliases = [club["name"], *club.get("aliases", [])]
        print(f"Hentar lag for {club['name']} ({club_id})")
        teams_payload = api_get(base_url, f"clubs/{club_id}/teams", cid, cwd)
        teams = collection(teams_payload, "Teams", "teams", "Results", "results")

        for team in teams:
            team_id = first(team, "TeamId", "Id", "teamId", "id")
            if not team_id:
                continue
            matches_payload = api_get(base_url, f"teams/{team_id}/matches", cid, cwd)
            raw_matches = collection(matches_payload, "Matches", "matches", "Results", "results")
            for raw in raw_matches:
                normalized = normalize_match(raw, aliases, minimum_age)
                if normalized:
                    matches_by_id[normalized["id"]] = normalized

    matches = sorted(matches_by_id.values(), key=lambda m: (m["date"], m["time"]), reverse=True)
    if not matches:
        print("Ingen publiserbare ferdigspilte kampar funne. Beheld eksisterande data/matches.json.")
        return 0

    existing = load_json(OUTPUT_PATH) if OUTPUT_PATH.exists() else {}
    output = {
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "photoSubmitUrl": existing.get("photoSubmitUrl", "#"),
        "matches": matches,
    }
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Skreiv {len(matches)} verifiserte resultat til {OUTPUT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FEIL: {exc}", file=sys.stderr)
        raise
