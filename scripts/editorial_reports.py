#!/usr/bin/env python3
"""Nynorsk, fact-constrained editorial summaries of completed youth matches.

This is deterministic editorial generation, not a claim of eyewitness reporting.
Every storyline must be traceable to final score, half-time, or NFF goal events.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATCHES = ROOT / "data" / "matches.json"
OUTPUT = ROOT / "data" / "editorial-reports.json"
VERSION = 1

NUMBERS = {0: "null", 1: "eitt", 2: "to", 3: "tre", 4: "fire", 5: "fem",
           6: "seks", 7: "sju", 8: "åtte", 9: "ni", 10: "ti"}
DURATION = {13: 70, 14: 70, 15: 80, 16: 80, 17: 90, 18: 90, 19: 90}


def number(n):
    return NUMBERS.get(n, str(n))


def final(match):
    h, a = match.get("homeScore"), match.get("awayScore")
    return isinstance(h, int) and not isinstance(h, bool) and isinstance(a, int) and not isinstance(a, bool) and h >= 0 and a >= 0


def youth(match):
    return bool(re.fullmatch(r"[GJ]\d{2}", str(match.get("age", "")).upper()))


def winner_side(match):
    if match["homeScore"] == match["awayScore"]:
        return None
    return "home" if match["homeScore"] > match["awayScore"] else "away"


def age_duration(match):
    found = re.fullmatch(r"[GJ](\d{2})", str(match.get("age", "")).upper())
    return DURATION.get(int(found.group(1))) if found else None


def anonymous(event):
    player = str(event.get("player") or "").casefold().strip()
    return (not player or event.get("personUnavailable") or
            "personinfo" in player or "personinformasjon" in player or
            "skjult" in player or "tilgjengeleg" in player or
            "tilgjengelig" in player or player in {"mål", "mal", "ukjend", "ukjent"})


def own_goal(event):
    label = str(event.get("label") or "").casefold()
    return "sjølv" in label or "selv" in label or "own goal" in label


def goal_data(match):
    goals = [e for e in (match.get("events") or []) if e.get("type") == "goal" and e.get("team") in {"home", "away"}]
    count = Counter(e["team"] for e in goals)
    complete = count["home"] == match["homeScore"] and count["away"] == match["awayScore"]
    # Some NFF pages encode an unknown minute as 0. Equal-minute opposing goals
    # have no reliable order in flattened markup: do not infer dramatic sequencing.
    minutes = [e.get("minute") for e in goals]
    chronology = complete and bool(goals) and all(type(x) is int and x > 0 for x in minutes)
    if chronology:
        per_minute = {}
        for e in goals:
            per_minute.setdefault(e["minute"], set()).add(e["team"])
        chronology = not any(len(sides) > 1 for sides in per_minute.values())
    ordered = sorted(goals, key=lambda e: e.get("minute") or 0) if chronology else []
    return goals, complete, ordered


def scorers(goals):
    return Counter(str(e["player"]).strip() for e in goals if not anonymous(e) and not own_goal(e))


def score_at_event(match, ordered):
    scores = {"home": 0, "away": 0}
    out = []
    for e in ordered:
        before = dict(scores)
        scores[e["team"]] += 1
        out.append((e, before, dict(scores)))
    return out


def late_decider(match, ordered):
    side = winner_side(match)
    duration = age_duration(match)
    if not side or not duration or not ordered:
        return None
    states = score_at_event(match, ordered)
    other = "away" if side == "home" else "home"
    for i, (event, before, after) in enumerate(states):
        minute = event["minute"]
        if event["team"] != side or minute < duration - 7:
            continue
        if before[side] != before[other] or after[side] <= after[other]:
            continue
        if all(later[2][side] > later[2][other] for later in states[i:]):
            return event, after
    return None


def did_turn(match, ordered):
    side = winner_side(match)
    if not side:
        return False
    other = "away" if side == "home" else "home"
    half = re.fullmatch(r"\s*(\d+)\s*[-–:]\s*(\d+)\s*", str(match.get("halfTime") or ""))
    if half:
        values = {"home": int(half.group(1)), "away": int(half.group(2))}
        if values[side] < values[other]:
            return True
    if ordered:
        return any(after[side] < after[other] for _, _, after in score_at_event(match, ordered))
    return False


def safe_half(match):
    found = re.fullmatch(r"\s*(\d+)\s*[-–:]\s*(\d+)\s*", str(match.get("halfTime") or ""))
    if not found:
        return None
    h, a = map(int, found.groups())
    if h > match["homeScore"] or a > match["awayScore"]:
        return None
    return h, a


def generate(match):
    if not youth(match) or not final(match):
        return None
    home, away = match["home"], match["away"]
    hs, ac = match["homeScore"], match["awayScore"]
    side = winner_side(match)
    winning = match[side] if side else None
    losing = match["away" if side == "home" else "home"] if side else None
    win_goals = match["homeScore" if side == "home" else "awayScore"] if side else None
    lose_goals = match["awayScore" if side == "home" else "homeScore"] if side else None
    result = f"{win_goals}–{lose_goals}" if side else f"{hs}–{ac}"
    goals, complete, ordered = goal_data(match)
    known = scorers(e for e in goals if side and e["team"] == side)
    name, count = known.most_common(1)[0] if known else (None, 0)
    total_known_goals = sum(known.values())
    all_by_one = bool(side and complete and win_goals >= 3 and
                      count == win_goals and total_known_goals == win_goals)
    decisive = late_decider(match, ordered) if complete else None
    comeback = did_turn(match, ordered) if side else False
    half = safe_half(match)
    total = hs + ac

    if all_by_one:
        title = f"{name} herja framfor mål – {winning} vann {result}"
    elif decisive:
        event, _ = decisive
        if not anonymous(event) and not own_goal(event):
            title = f"{event['player']} avgjorde seint for {winning}"
        else:
            title = f"Seint vinnarmål sikra {winning} sigeren"
    elif comeback:
        title = f"{winning} snudde kampen og vann {result}"
    elif side and count >= 4:
        title = f"{number(count).capitalize()} mål av {name} då {winning} vann"
    elif side and count == 3:
        title = f"Hattrick av {name} då {winning} vann"
    elif side and abs(hs-ac) >= 5:
        title = f"{winning} vann stort mot {losing}"
    elif not side and total >= 6:
        title = f"Målfest og poengdeling mellom {home} og {away}"
    elif not side and total == 0:
        title = f"Mållaus kamp mellom {home} og {away}"
    elif not side:
        title = f"Poengdeling mellom {home} og {away}"
    else:
        title = f"{winning} vann {result} mot {losing}"

    competition = str(match.get("competition") or match.get("age") or "aldersbestemt fotball")
    if side:
        lead = f"{winning} vann {result} mot {losing} i {competition}."
    else:
        lead = f"{home} og {away} spelte {hs}–{ac} i {competition}."
    if all_by_one:
        lead += f" {name} stod for alle dei {number(win_goals)} måla til {winning}."
    elif decisive:
        event, _ = decisive
        lead += f" Vinnarmålet kom i det {event['minute']}. minuttet."
    elif comeback:
        lead += f" {winning} måtte hente inn eit underlag før sigeren var sikra."
    elif side and count >= 3:
        lead += f" {name} skåra {number(count)} av måla."
    elif not side and total >= 6:
        lead += f" Heile {number(total)} mål vart registrerte."

    paras = []
    if half:
        paras.append(f"Til pause stod det {half[0]}–{half[1]}.")

    if ordered:
        first = ordered[0]
        first_score = "1–0" if first["team"] == "home" else "0–1"
        who = first.get("player")
        by = str(who).strip() if not anonymous(first) and not own_goal(first) else match[first["team"]]
        paras.append(f"{by} stod for det første målet etter {first['minute']} minutt og sende stillinga til {first_score}.")
        if decisive:
            event, after = decisive
            who = str(event.get("player") or "").strip()
            actor = who if not anonymous(event) and not own_goal(event) else winning
            paras.append(
                f"I det {event['minute']}. minuttet skåra {actor} for {winning}. "
                f"Målet sende laget i leiinga for godt, og stillinga vart {after['home']}–{after['away']}."
            ) if actor != winning else paras.append(
                f"I det {event['minute']}. minuttet kom målet som sende {winning} i leiinga for godt. "
                f"Då var stillinga {after['home']}–{after['away']}."
            )
        elif comeback:
            paras.append(f"{winning} var bakpå undervegs, men snudde oppgjeret til siger.")
    elif comeback and half:
        paras.append(f"{winning} låg under ved pause, men snudde kampen etter kvilen.")

    if name and count >= 3:
        if all_by_one:
            paras.append(f"{name} stod for samtlege {number(win_goals)} mål til vinnarlaget og sikra seg hattrick.")
        else:
            paras.append(f"{name} noterte seg for {number(count)} mål for {winning}" + (" og sikra seg hattrick." if count == 3 else "."))
    elif name and count == 2 and complete:
        paras.append(f"{name} noterte seg for to av måla til {winning}.")
    if not complete:
        if goals:
            paras.append("NFF har ikkje ei fullstendig målrekkje registrert for oppgjeret. Berre stadfesta målscorarar og minutt blir viste.")
        else:
            paras.append("Det er førebels ikkje registrert ei detaljert målrekkje frå kampen hos NFF.")

    # Do not manufacture tactical superiority, possession, chances, player roles
    # or the time of unregistered goals from a final score alone.
    return {
        "title": title,
        "lead": lead,
        "paragraphs": paras,
        "mode": "automatic",
        "basis": "NFF-kampdata",
        "completeGoalTimeline": complete,
        "generatorVersion": VERSION,
    }


def build(document):
    out = {}
    for match in document.get("matches", []):
        item = generate(match)
        if item:
            out[str(match.get("matchNumber") or match.get("id"))] = item
    return {"version": VERSION, "reports": out}


def main():
    result = build(json.loads(MATCHES.read_text(encoding="utf-8")))
    body = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != body:
        OUTPUT.write_text(body, encoding="utf-8")
    print(f"Editorial reports: {len(result['reports'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
