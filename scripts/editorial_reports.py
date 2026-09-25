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
VERSION = 3

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
    return bool(event.get("ownGoal")) or "sjølv" in label or "selv" in label or "own goal" in label


def own_goal_team(match, event):
    side = event.get("playerTeam")
    return match.get(side) if side in {"home", "away"} else None


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
    half = safe_half(match)
    if half:
        values = {"home": half[0], "away": half[1]}
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


def half_time_split(ordered, half):
    """Use the official pause score to place halftime without guessing a minute."""
    if half is None or not ordered:
        return None
    boundary = sum(half)
    if boundary > len(ordered):
        return None
    before = Counter(e["team"] for e in ordered[:boundary])
    if (before["home"], before["away"]) != half:
        return None
    if 0 < boundary < len(ordered) and ordered[boundary-1]["minute"] == ordered[boundary]["minute"]:
        return None
    return boundary


def minute_clause(minutes):
    if len(minutes) == 1:
        return f"i det {minutes[0]}. minuttet"
    values = [str(m) for m in minutes]
    return "i minutta " + ", ".join(values[:-1]) + " og " + values[-1]


def goal_sentence(match, item, first=False, decisive=False):
    event, before, after = item
    side = event["team"]
    other = "away" if side == "home" else "home"
    team = match[side]
    when = minute_clause([event["minute"]])
    score = f"{after['home']}–{after['away']}"
    if own_goal(event):
        owner = own_goal_team(match, event)
        subject = f"Eit sjølvmål frå {owner}" if owner else "Eit sjølvmål"
        if first:
            return f"{subject} {when} gav {team} leiinga."
        if decisive:
            return f"{subject} {when} sende {team} i leiinga for godt."
        if before[side] > before[other]:
            return f"{subject} {when} auka leiinga til {score} for {team}."
        if before[side] == before[other]:
            return f"{subject} {when} gav {team} leiinga."
        if after[side] == after[other]:
            return f"{subject} {when} gav {team} utlikninga til {score}."
        return f"{subject} {when} reduserte til {score} for {team}."

    named = not anonymous(event)
    player = str(event["player"]).strip() if named else team
    if first:
        return (f"{player} gav {team} leiinga {when}." if named
                else f"{team} tok leiinga {when}.")
    if decisive:
        return (f"{player} skåra vinnarmålet for {team} {when}." if named
                else f"{team} skåra vinnarmålet {when}.")
    if after[side] == after[other]:
        return (f"{player} utlikna til {score} for {team} {when}." if named
                else f"{team} utlikna til {score} {when}.")
    if before[side] == before[other]:
        return (f"{player} sende {team} i leiinga {when}." if named
                else f"{team} tok leiinga {when}.")
    if before[side] > before[other]:
        return (f"{player} auka til {score} for {team} {when}." if named
                else f"{team} auka leiinga til {score} {when}.")
    return (f"{player} reduserte til {score} for {team} {when}." if named
            else f"{team} reduserte til {score} {when}.")


def chronological_paragraphs(match, ordered, half, decisive):
    states = score_at_event(match, ordered)
    boundary = half_time_split(ordered, half)
    paras = []
    i = 0
    while i < len(states):
        if boundary is not None and i == boundary:
            paras.append(f"Til pause stod det {half[0]}–{half[1]}.")

        event, before, after = states[i]
        side = event["team"]
        other = "away" if side == "home" else "home"
        j = i
        if i > 0 and not own_goal(event) and anonymous(event):
            while j < len(states):
                current, old, new = states[j]
                if (current["team"] != side or own_goal(current) or not anonymous(current)
                    or (decisive and current is decisive[0])
                    or old[side] <= old[other] or new[side] <= new[other]
                    or (boundary is not None and j == boundary and j > i)
                    or (j > i and current["minute"] == states[j - 1][0]["minute"])):
                    break
                j += 1
        if j - i >= 2:
            minutes = [states[k][0]["minute"] for k in range(i, j)]
            paras.append(f"{match[side]} auka leiinga med mål {minute_clause(minutes)}.")
            i = j
            continue
        paras.append(goal_sentence(
            match, states[i], first=(i == 0),
            decisive=bool(decisive and event is decisive[0]),
        ))
        i += 1

    if boundary is not None and boundary == len(states):
        paras.append(f"Til pause stod det {half[0]}–{half[1]}.")
    return paras


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
    goal_data_trusted = match.get("goalTimelineVerified") is not False
    goals, complete, ordered = goal_data(match) if goal_data_trusted else ([], False, [])
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
        if own_goal(event):
            title = f"Seint sjølvmål gav {winning} sigeren"
        elif not anonymous(event):
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
        if own_goal(event):
            owner = own_goal_team(match, event)
            lead += (f" Eit sjølvmål frå {owner} i det {event['minute']}. minuttet avgjorde kampen."
                     if owner else f" Eit sjølvmål i det {event['minute']}. minuttet avgjorde kampen.")
        else:
            lead += f" Vinnarmålet kom i det {event['minute']}. minuttet."
    elif comeback:
        lead += f" {winning} måtte hente inn eit underlag før sigeren var sikra."
    elif side and count >= 3:
        lead += f" {name} skåra {number(count)} av måla."
    elif not side and total >= 6:
        lead += f" Heile {number(total)} mål vart registrerte."

    paras = chronological_paragraphs(match, ordered, half, decisive) if ordered else []
    if not ordered:
        if half:
            paras.append(f"Til pause stod det {half[0]}–{half[1]}.")
        for event in sorted(goals, key=lambda e: e.get("minute") if type(e.get("minute")) is int else 999):
            if not own_goal(event):
                continue
            owner = own_goal_team(match, event)
            subject = f"Eit sjølvmål frå {owner}" if owner else "Eit sjølvmål"
            when = f" {minute_clause([event['minute']])}" if type(event.get("minute")) is int and event["minute"] > 0 else ""
            paras.append(f"{subject}{when} vart kreditert {match[event['team']]}.")
        if complete and goals:
            paras.append("Nokre mål er registrerte på same minutt, så den innbyrdes rekkjefølgja er ikkje stadfesta.")

    if not ordered and name and count >= 3:
        if all_by_one:
            paras.append(f"{name} stod for samtlege {number(win_goals)} mål til vinnarlaget og sikra seg hattrick.")
        else:
            paras.append(f"{name} noterte seg for {number(count)} mål for {winning}" + (" og sikra seg hattrick." if count == 3 else "."))
    elif not ordered and name and count == 2 and complete:
        paras.append(f"{name} noterte seg for to av måla til {winning}.")

    if not ordered and not side:
        for team_side, team in (("home", home), ("away", away)):
            players = scorers(e for e in goals if e["team"] == team_side)
            multi = [(player, n) for player, n in players.most_common() if n >= 2]
            if multi:
                if len(multi) == 1:
                    player, n = multi[0]
                    paras.append(f"{player} skåra {number(n)} av måla til {team}.")
                else:
                    parts = [f"{player} ({number(n)} mål)" for player, n in multi[:3]]
                    paras.append(f"For {team} noterte desse seg for fleire mål: " + ", ".join(parts) + ".")

    if not ordered and half and (hs + ac) > sum(half) and not decisive and not goals:
        h_after, a_after = hs - half[0], ac - half[1]
        if h_after > 0 and a_after > 0:
            paras.append(f"Etter pause fekk {home} {number(h_after)} mål og {away} {number(a_after)} mål.")
        elif h_after > 0:
            paras.append(f"Etter pause fekk {home} " + ("eitt mål til." if h_after == 1 else f"{number(h_after)} nye mål."))
        elif a_after > 0:
            paras.append(f"Etter pause fekk {away} " + ("eitt mål til." if a_after == 1 else f"{number(a_after)} nye mål."))

    if not complete:
        if not goal_data_trusted:
            paras.append("Detaljert målrekkje er ikkje stadfesta. Inntil vidare viser vi berre det stadfesta sluttresultatet.")
        elif goals:
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
