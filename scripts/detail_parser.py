from __future__ import annotations

import re
from bs4 import BeautifulSoup


def clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def compact(value) -> str:
    return re.sub(r"\s+", "", clean(value).casefold())


def integer(value):
    m = re.search(r"-?\d+", clean(value).replace("−", "-"))
    return int(m.group()) if m else None


def parse_score(value: str):
    m = re.fullmatch(r"\s*(\d+)\s*[-–]\s*(\d+)\s*", clean(value))
    return (int(m.group(1)), int(m.group(2))) if m else None


def _lines(soup: BeautifulSoup):
    raw = [clean(x) for x in soup.stripped_strings if clean(x)]
    lines = []
    i = 0
    while i < len(raw):
        value = raw[i]
        if (
            re.fullmatch(r"\d{1,3}", value)
            and i + 1 < len(raw)
            and raw[i + 1] in {"'", "’", "′"}
        ):
            lines.append(f"{value}'")
            i += 2
            continue
        m = re.fullmatch(r"(\d{1,3})\s*['’′]", value)
        lines.append(f"{m.group(1)}'" if m else value)
        i += 1
    return lines


def _player_pairs(tokens):
    controls = {
        "kaptein", "kap tein", "debutant", "deb utant",
        "startoppstilling:", "startoppstilling",
        "innbyttere:", "innbyttere", "kamptropper",
        "kamphendelser", "dommere", "tidligere oppgjør",
    }
    players = []
    i = 0
    while i < len(tokens):
        token = clean(tokens[i])
        if not re.fullmatch(r"\d{1,3}", token):
            i += 1
            continue
        number = int(token)
        j = i + 1
        while j < len(tokens):
            candidate = clean(tokens[j])
            folded = candidate.casefold()
            if (
                candidate
                and folded not in controls
                and not re.fullmatch(r"\d{1,3}", candidate)
                and not re.fullmatch(r"\d{1,3}'", candidate)
                and not any(word in folded for word in (
                    "spillemål", "straffemål", "selvmål",
                    "advarsel", "utvisning"
                ))
            ):
                players.append({"number": number, "name": candidate})
                i = j + 1
                break
            j += 1
        else:
            i += 1

    seen = set()
    unique = []
    for player in players:
        key = player["name"].casefold()
        if key not in seen:
            seen.add(key)
            unique.append(player)
    return unique


def _extract_lineups(lines):
    joined = " ".join(lines[:180])
    starter_limit = 11
    form_match = re.search(r"Turnering:\s*.{0,100}?\b(5|7|9|11)er\b", joined, re.I)
    if form_match:
        starter_limit = int(form_match.group(1))

    start_indexes = [
        i for i, line in enumerate(lines)
        if compact(line).startswith("startoppstilling")
    ]
    result = {}
    for pos, start_i in enumerate(start_indexes[:2]):
        side = "home" if pos == 0 else "away"
        next_start = (
            start_indexes[pos + 1]
            if pos + 1 < len(start_indexes)
            else len(lines)
        )

        end_i = next_start
        for j in range(start_i + 1, next_start):
            token = compact(lines[j])
            if token in {
                "kamphendelser", "dommere", "tidligereoppgjør",
                "oversiktovertidligereoppgjørmellomlagene."
            }:
                end_i = j
                break

        bench_i = next(
            (
                j for j in range(start_i + 1, end_i)
                if compact(lines[j]).startswith("innbyttere")
            ),
            None,
        )
        starter_end = bench_i if bench_i is not None else end_i
        starters = _player_pairs(lines[start_i + 1:starter_end])
        bench = _player_pairs(lines[bench_i + 1:end_i]) if bench_i is not None else []
        if len(starters) > starter_limit:
            overflow = starters[starter_limit:]
            starters = starters[:starter_limit]
            bench = overflow + bench
        if starters or bench:
            result[side] = {"starters": starters, "bench": bench}

    return result or None


def _player_map(lineups):
    result = {}
    for side, lineup in (lineups or {}).items():
        for player in (lineup.get("starters") or []) + (lineup.get("bench") or []):
            result[player["name"]] = side
    return result


def _known_player(segment, players, side, reverse=False):
    names = sorted(players, key=len, reverse=True)
    indexes = range(len(segment) - 1, -1, -1) if reverse else range(len(segment))
    for i in indexes:
        folded = clean(segment[i]).casefold()
        for name in names:
            if players[name] != side:
                continue
            if folded == name.casefold() or name.casefold() in folded:
                return name, i
    return None, None


def _event_kind(segment):
    terms = (
        ("straffemål", "goal"),
        ("selvmål", "goal"),
        ("spillemål", "goal"),
        ("advarsel", "yellow_card"),
        ("gult kort", "yellow_card"),
        ("gultkort", "yellow_card"),
        ("utvisning", "red_card"),
        ("rødt kort", "red_card"),
        ("raudt kort", "red_card"),
        ("rødtkort", "red_card"),
        ("raudtkort", "red_card"),
    )
    for line in segment:
        folded = clean(line).casefold()
        for term, kind in terms:
            if term in folded:
                return kind, clean(line)
    return None, None


def _substitution(segment, players, side):
    player_in = None
    player_out = None
    for i, line in enumerate(segment):
        value = clean(line)
        m_in = re.search(r"\binn\s*:\s*(.*)$", value, re.I)
        m_out = re.search(r"\but\s*:\s*(.*)$", value, re.I)
        if m_in:
            player_in = clean(m_in.group(1))
            if not player_in and i + 1 < len(segment):
                player_in = clean(segment[i + 1])
        if m_out:
            player_out = clean(m_out.group(1))
            if not player_out and i + 1 < len(segment):
                player_out = clean(segment[i + 1])

    detected = players.get(player_in) or players.get(player_out)
    if (player_in or player_out) and detected == side:
        return {
            "type": "substitution",
            "team": side,
            "playerIn": player_in,
            "playerOut": player_out,
        }
    return None


def _event_from_segment(segment, players, side, reverse=False):
    sub = _substitution(segment, players, side)
    if sub:
        return sub

    player, player_i = _known_player(segment, players, side, reverse=reverse)
    if not player:
        return None

    lo = max(0, player_i - 2)
    hi = min(len(segment), player_i + 3)
    event_type, label = _event_kind(segment[lo:hi])
    if not event_type:
        return None

    return {
        "type": event_type,
        "team": side,
        "player": player,
        "label": label,
    }


def _extract_events(lines, lineups):
    players = _player_map(lineups)
    if not players:
        return []

    minute_indexes = [
        i for i, line in enumerate(lines)
        if re.fullmatch(r"\d{1,3}'", clean(line))
    ]
    events = []
    for n, idx in enumerate(minute_indexes):
        minute = integer(lines[idx])
        prev_i = minute_indexes[n - 1] if n else -1
        next_i = (
            minute_indexes[n + 1]
            if n + 1 < len(minute_indexes)
            else len(lines)
        )

        # NFF's desktop timeline is two-column. When linearized,
        # home events appear before the minute and away events after it.
        before = lines[max(prev_i + 1, idx - 8):idx]
        after = lines[idx + 1:min(next_i, idx + 9)]

        for item in (
            _event_from_segment(before, players, "home", reverse=True),
            _event_from_segment(after, players, "away", reverse=False),
        ):
            if item:
                item["minute"] = minute
                events.append(item)

    seen = set()
    unique = []
    for item in events:
        key = (
            item.get("minute"), item.get("type"), item.get("team"),
            item.get("player"), item.get("playerIn"), item.get("playerOut"),
        )
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return sorted(unique, key=lambda item: item.get("minute") or 0)



def _page_score(lines, home=None, away=None):
    # Prefer a score located close to the two team names in the match header.
    if home and away:
        home_cf = clean(home).casefold()
        away_cf = clean(away).casefold()
        home_hits = [i for i, line in enumerate(lines[:160]) if clean(line).casefold() == home_cf]
        away_hits = [i for i, line in enumerate(lines[:160]) if clean(line).casefold() == away_cf]
        for hi in home_hits:
            for ai in away_hits:
                lo, high = sorted((hi, ai))
                if high - lo <= 30:
                    for line in lines[lo:high + 1]:
                        score = parse_score(line)
                        if score:
                            return score

    # Fallback: the match header is near the top of the document.
    for line in lines[:80]:
        if line.startswith("(") and line.endswith(")"):
            continue
        score = parse_score(line)
        if score:
            return score
    return None


def _reconcile_goal_events(events, final_score):
    if not final_score:
        return events

    allowed = {"home": int(final_score[0]), "away": int(final_score[1])}
    kept = []
    goal_counts = {"home": 0, "away": 0}

    # Keep events in chronological order. If flattened two-column markup creates
    # an extra goal, discard only goals that would make a team's event count
    # exceed the actual final score. Never invent missing goals.
    for item in sorted(events, key=lambda x: x.get("minute") or 0):
        if item.get("type") != "goal":
            kept.append(item)
            continue
        side = item.get("team")
        if side not in allowed:
            continue
        if goal_counts[side] >= allowed[side]:
            continue
        goal_counts[side] += 1
        kept.append(item)
    return kept


def parse_detail(html: str, home: str | None = None, away: str | None = None):
    soup = BeautifulSoup(html, "html.parser")
    text = clean(soup.get_text(" ", strip=True))
    lines = _lines(soup)
    result = {"events": []}

    aliases = {
        "dommer": "referee",
        "hoveddommer": "referee",
        "hd": "referee",
        "assdommer1": "assistant1",
        "assistentdommer1": "assistant1",
        "ad1": "assistant1",
        "assdommer2": "assistant2",
        "assistentdommer2": "assistant2",
        "ad2": "assistant2",
        "fjerdedommer": "fourthOfficial",
        "dommerveileder": "refereeObserver",
    }
    officials = {}
    for tr in soup.find_all("tr"):
        cells = [
            clean(c.get_text(" ", strip=True))
            for c in tr.find_all(["th", "td"])
        ]
        if len(cells) < 2:
            continue
        role = compact(cells[0]).replace(".", "")
        if role in aliases and cells[1]:
            officials[aliases[role]] = cells[1]
    if officials:
        result["officials"] = officials
        if officials.get("referee"):
            result["referee"] = officials["referee"]

    for tr in soup.find_all("tr"):
        cells = [
            clean(c.get_text(" ", strip=True))
            for c in tr.find_all(["th", "td"])
        ]
        if len(cells) < 2:
            continue
        label = compact(cells[0])
        value = cells[1]
        if "tilskodar" in label or "tilskuer" in label:
            n = integer(value)
            if n is not None:
                result["attendance"] = n
        if label in {"pause", "pauseresultat", "ht"} and parse_score(value):
            result["halfTime"] = clean(value)

    if "halfTime" not in result:
        for line in lines[:100]:
            m = re.fullmatch(r"\(\s*(\d+)\s*[-–]\s*(\d+)\s*\)", line)
            if m:
                result["halfTime"] = f"{m.group(1)}–{m.group(2)}"
                break

    lineups = _extract_lineups(lines)
    if lineups:
        result["lineups"] = lineups

    result["events"] = _reconcile_goal_events(
        _extract_events(lines, lineups),
        _page_score(lines, home, away),
    )

    folded = text.casefold()
    no_events = "ingen kamphendelser registrert" in folded
    no_squad = "kamptropp ikke publisert eller registrert" in folded
    result["hasRegisteredEvents"] = bool(result["events"]) or not no_events
    result["hasPublishedSquad"] = bool(lineups) and not no_squad
    return result
# markup revision 2
# retry after pattern fix
