#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
import time
import unicodedata
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
MATCHES_PATH = ROOT / "data" / "matches.json"
REPORTS_PATH = ROOT / "data" / "reports.json"
STATE_PATH = ROOT / "data" / "report-state.json"
CONFIG_PATH = ROOT / "config" / "report-sources.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "nn-NO,nb-NO;q=0.9,no;q=0.8,en;q=0.5",
    "Cache-Control": "no-cache",
}
LOCAL_TOKENS = [
    "Vestnes Varfjell","Tomrefjord","Fiksdal/Rekdal","Ørskog","Stordal",
    "Skodje","Brattvåg","Ravn","Norborg","HaNo","Harøy","Lepsøy","Hildre"
]
STOP_WORDS = {
    "il","fk","bk","sk","idrettslag","fotball","2","3","4","7er","9er","11er",
    "menn","kvinner","g13","g14","g15","g16","j13","j14","j15","j16"
}

def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default

def save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def now_local():
    return datetime.now().astimezone()

def parse_dt(match):
    value = f"{match.get('date','')}T{match.get('time') or '12:00'}:00"
    return datetime.fromisoformat(value).replace(tzinfo=now_local().tzinfo)

def strip_marks(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in text if not unicodedata.combining(ch))

def norm(value):
    value = strip_marks(value).casefold()
    value = value.replace("ø","o").replace("æ","ae").replace("å","a")
    return re.sub(r"[^a-z0-9]+", " ", value).strip()

def team_words(team):
    words = [w for w in norm(team).split() if w not in STOP_WORDS and len(w) >= 3]
    return list(dict.fromkeys(words))

def is_local(match):
    joined = f"{match.get('home','')} {match.get('away','')}".casefold()
    return any(token.casefold() in joined for token in LOCAL_TOKENS)

def matching_sources(match, sources):
    joined = f"{match.get('home','')} {match.get('away','')}".casefold()
    out = []
    for src in sources:
        if not src.get("enabled", True):
            continue
        if any(token.casefold() in joined for token in src.get("teamTokens", [])):
            out.append(src)
    return out

def safe_url(url, source):
    try:
        p = urlparse(url)
    except Exception:
        return None
    if p.scheme not in {"http","https"}:
        return None
    if p.hostname not in set(source.get("allowedHosts", [])):
        return None
    clean, _ = urldefrag(url)
    return clean

ROBOTS = {}

def robots_allowed(url, timeout):
    p = urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in ROBOTS:
        parser = RobotFileParser()
        parser.set_url(urljoin(base, "/robots.txt"))
        try:
            parser.read()
            ROBOTS[base] = parser
        except Exception:
            ROBOTS[base] = None
    parser = ROBOTS.get(base)
    return True if parser is None else parser.can_fetch(HEADERS["User-Agent"], url)

def request(session, url, timeout):
    try:
        if not robots_allowed(url, timeout):
            return None
        r = session.get(url, timeout=timeout, allow_redirects=True)
        if r.status_code != 200:
            return None
        ctype = r.headers.get("content-type","").lower()
        if "html" not in ctype and "text" not in ctype:
            return None
        return r.text
    except requests.RequestException:
        return None

def extract_links(html, base_url, source):
    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = safe_url(urljoin(base_url, a.get("href")), source)
        if not href or href in seen:
            continue
        if re.search(r"\.(?:jpg|jpeg|png|gif|svg|pdf|zip|docx?)(?:\?|$)", href, re.I):
            continue
        text = " ".join(a.stripped_strings).strip()
        if not text and not any(h in href.casefold() for h in source.get("pathHints", [])):
            continue
        seen.add(href)
        items.append((href, text))
    return items

def score_link(url, anchor, match, source):
    hay = norm(f"{anchor} {url}")
    score = 0
    for team in (match.get("home",""), match.get("away","")):
        words = team_words(team)
        if any(w in hay for w in words):
            score += 4
    for hint in source.get("pathHints", []):
        if norm(hint) in hay:
            score += 2
    if any(k in hay for k in ("kamp","seier","siger","tap","uavgjort","poeng","mal")):
        score += 1
    return score

def article_text(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script","style","nav","footer","header","form","aside"]):
        tag.decompose()
    root = soup.find("article") or soup.find("main") or soup.body or soup
    chunks = []
    for el in root.find_all(["h1","h2","h3","p","li"]):
        text = " ".join(el.stripped_strings).strip()
        if len(text) >= 25:
            chunks.append(text)
    return "\n".join(chunks)

def score_article(text, match, source):
    n = norm(text)
    score = 0
    home_words = team_words(match.get("home",""))
    away_words = team_words(match.get("away",""))
    source_words = []
    for token in source.get("teamTokens", []):
        source_words.extend(team_words(token))
    opponent_words = away_words if any(w in n for w in home_words) else home_words
    if any(w in n for w in home_words):
        score += 5
    if any(w in n for w in away_words):
        score += 5
    if any(w in n for w in source_words):
        score += 2
    if any(w in n for w in opponent_words):
        score += 2

    hs, as_ = match.get("homeScore"), match.get("awayScore")
    if isinstance(hs, int) and isinstance(as_, int):
        patterns = [
            rf"\b{hs}\s*[-–:]\s*{as_}\b",
            rf"\b{as_}\s*[-–:]\s*{hs}\b",
        ]
        plain = strip_marks(text)
        if any(re.search(p, plain) for p in patterns):
            score += 8

    d = match.get("date","")
    if d:
        try:
            dt = datetime.fromisoformat(d)
            date_tokens = {
                str(dt.day),
                f"{dt.day:02d}.{dt.month:02d}",
                f"{dt.day}.{dt.month}",
                dt.strftime("%d.%m.%Y"),
            }
            if any(tok in text for tok in date_tokens):
                score += 2
        except ValueError:
            pass

    if len(text) > 500:
        score += 2
    return score

def split_sentences(text):
    parts = re.split(r"(?<=[.!?])\\s+(?=[A-ZÆØÅ0-9])", " ".join(str(text or "").split()))
    return [p.strip() for p in parts if 35 <= len(p.strip()) <= 320]

def source_side(match, source):
    tokens = [norm(x) for x in source.get("teamTokens", [])]
    home = norm(match.get("home",""))
    away = norm(match.get("away",""))
    home_hit = any(t and (t in home or home in t) for t in tokens)
    away_hit = any(t and (t in away or away in t) for t in tokens)
    if home_hit and not away_hit:
        return "home"
    if away_hit and not home_hit:
        return "away"
    return None

def article_context(text, match, source):
    sentences = split_sentences(text)
    if not sentences:
        return None

    cues = {
        "dominance": ("dominer", "styrte kampen", "kontrollerte kampen", "førande laget", "best i store delar"),
        "chances": ("sjans", "mulighet", "moglegheit", "avslutning", "avslutningar"),
        "even": ("jamn kamp", "jevn kamp", "jamt", "jevnt", "bølgja fram og tilbake", "bølget fram og tilbake"),
        "pressure": ("press", "trykk", "beleiring"),
        "comeback": ("snudde", "comeback", "henta inn", "utlikna", "utlignet"),
        "keeper": ("keeper", "målvakt", "redning", "redningar"),
        "woodwork": ("stolpe", "tverrligger", "tverrliggjar"),
    }

    source_team = match.get(source_side(match, source) or "home", "")
    source_words = team_words(source_team)
    scorer_names = [
        norm(e.get("player",""))
        for e in match.get("events",[])
        if e.get("type") == "goal" and e.get("player")
    ]

    best = []
    for sentence in sentences:
        n = norm(sentence)
        score = 0
        if any(w in n for w in source_words):
            score += 3
        if any(name and name in n for name in scorer_names):
            score += 2
        tags = []
        for tag, words in cues.items():
            if any(norm(word) in n for word in words):
                tags.append(tag)
                score += 2
        if tags and score >= 2:
            best.append((score, tags, sentence))
    if not best:
        return None

    best.sort(key=lambda x: x[0], reverse=True)
    tags = []
    for _, found_tags, _ in best[:3]:
        for tag in found_tags:
            if tag not in tags:
                tags.append(tag)

    team = source_team or source.get("name") or "laget"
    if "dominance" in tags:
        return f"Klubbreferatet skildrar {team} som det førande laget i store delar av kampen."
    if "comeback" in tags:
        return "Klubbreferatet peikar på at kampbiletet endra seg undervegs."
    if "even" in tags:
        return "Klubben skildrar kampen som jamn i periodar."
    if "pressure" in tags:
        return f"Ifølgje klubbreferatet hadde {team} ein periode med tydeleg press."
    if "chances" in tags:
        return f"Klubbreferatet fortel at {team} skapte fleire gode sjansar gjennom kampen."
    if "keeper" in tags:
        return "Klubbreferatet trekkjer fram fleire viktige redningar."
    if "woodwork" in tags:
        return "Klubbreferatet omtalar også avslutningar i treverket."
    return None

def score_complete(match):
    goals = [e for e in match.get("events",[]) if e.get("type") == "goal"]
    by_side = Counter(e.get("team") for e in goals)
    return by_side.get("home",0) == match.get("homeScore",0) and by_side.get("away",0) == match.get("awayScore",0)

def name_list(counter):
    parts = []
    for name, count in counter.most_common():
        parts.append(f"{name} ({count})" if count > 1 else name)
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + " og " + parts[-1]

def make_summary(match, source_name, article_text_value="", source=None):
    home, away = match["home"], match["away"]
    hs, as_ = int(match["homeScore"]), int(match["awayScore"])
    if hs > as_:
        first = f"{home} vann {hs}–{as_} mot {away}."
        winner_side = "home"
    elif as_ > hs:
        first = f"{away} vann {as_}–{hs} mot {home}."
        winner_side = "away"
    else:
        first = f"{home} og {away} spelte {hs}–{as_}."
        winner_side = None

    bits = [first]
    if match.get("halfTime"):
        bits.append(f"Til pause stod det {match['halfTime']}.")

    goals = [e for e in match.get("events",[]) if e.get("type") == "goal" and e.get("player")]
    if goals and score_complete(match):
        by_team = {"home":Counter(), "away":Counter()}
        for e in goals:
            if e.get("team") in by_team:
                by_team[e["team"]][e["player"]] += 1
        for side, team in (("home",home),("away",away)):
            names = name_list(by_team[side])
            if names:
                bits.append(f"For {team} stod {names} for måla.")
    elif goals:
        early = sorted(goals, key=lambda e: e.get("minute") or 999)[:2]
        if early:
            facts = []
            for e in early:
                minute = e.get("minute")
                facts.append(f"{e['player']} ({minute}. minutt)" if minute is not None else e["player"])
            bits.append("Blant dei registrerte målscorarane var " + " og ".join(facts) + ".")

    context = article_context(article_text_value, match, source or {}) if article_text_value else None
    if context:
        bits.append(context)
    elif source_name:
        bits.append("Klubbreferatet er brukt som tilleggsgrunnlag.")
    return " ".join(bits[:4])

def make_title(match):
    home, away = match["home"], match["away"]
    hs, as_ = int(match["homeScore"]), int(match["awayScore"])
    if hs > as_:
        return f"{home} vann {hs}–{as_}"
    if as_ > hs:
        return f"{away} vann {as_}–{hs}"
    return f"Poengdeling mellom {home} og {away}"

def due_for_check(match, state, retry_hours, force=False):
    if force:
        return True
    key = str(match.get("matchNumber") or match.get("id"))
    entry = state.get("matches",{}).get(key,{})
    if entry.get("done"):
        return False
    next_at = entry.get("nextCheckAt")
    if next_at:
        try:
            return now_local() >= datetime.fromisoformat(next_at)
        except ValueError:
            pass
    kickoff = parse_dt(match)
    return now_local() >= kickoff + timedelta(hours=retry_hours[0])

def update_retry(state, match, retry_hours, found=False):
    key = str(match.get("matchNumber") or match.get("id"))
    bucket = state.setdefault("matches",{}).setdefault(key,{})
    attempts = int(bucket.get("attempts",0))
    bucket["attempts"] = attempts + 1
    bucket["lastCheckAt"] = now_local().isoformat(timespec="seconds")
    if found:
        bucket["done"] = True
        bucket.pop("nextCheckAt",None)
        return
    if attempts + 1 >= len(retry_hours):
        bucket["done"] = True
        bucket["reason"] = "window_expired"
        bucket.pop("nextCheckAt",None)
        return
    kickoff = parse_dt(match)
    bucket["nextCheckAt"] = (kickoff + timedelta(hours=retry_hours[attempts + 1])).isoformat(timespec="seconds")

def main():
    force = "--force" in sys.argv
    cfg = load_json(CONFIG_PATH, {"settings":{},"sources":[]})
    settings = cfg.get("settings",{})
    retry_hours = settings.get("retryHours",[3,8,18,36,72,120])
    timeout = int(settings.get("requestTimeoutSeconds",12))
    lookback = int(settings.get("lookbackDays",7))
    max_indexes = int(settings.get("maxIndexRequestsPerRun",8))
    max_articles = int(settings.get("maxArticleRequestsPerRun",8))
    max_candidates = int(settings.get("maxCandidatesPerSource",6))

    matches_doc = load_json(MATCHES_PATH, {"matches":[]})
    reports_doc = load_json(REPORTS_PATH, {"reports":{}})
    reports = reports_doc.setdefault("reports",{})
    state = load_json(STATE_PATH, {"version":1,"matches":{}})

    cutoff = now_local().date() - timedelta(days=lookback)
    candidates = []
    for match in matches_doc.get("matches",[]):
        if not is_local(match):
            continue
        if str(match.get("matchNumber")) in reports or match.get("id") in reports:
            continue
        try:
            mdate = datetime.fromisoformat(match["date"]).date()
        except Exception:
            continue
        if mdate < cutoff:
            continue
        if not due_for_check(match, state, retry_hours, force):
            continue
        sources = matching_sources(match, cfg.get("sources",[]))
        if sources:
            candidates.append((match,sources))

    if not candidates:
        print("No report work due.")
        return 0

    session = requests.Session()
    session.headers.update(HEADERS)
    index_cache = {}
    index_requests = 0
    article_requests = 0
    found_count = 0
    checked = 0

    for match, sources in candidates:
        if index_requests >= max_indexes or article_requests >= max_articles:
            break
        found = None

        for source in sources:
            link_pool = []
            for index_url in source.get("indexUrls",[]):
                if index_requests >= max_indexes:
                    break
                if index_url not in index_cache:
                    html = request(session, index_url, timeout)
                    index_requests += 1
                    time.sleep(0.35)
                    index_cache[index_url] = extract_links(html, index_url, source) if html else []
                link_pool.extend(index_cache[index_url])

            ranked = []
            seen = set()
            for url, anchor in link_pool:
                if url in seen:
                    continue
                seen.add(url)
                score = score_link(url, anchor, match, source)
                if score > 0:
                    ranked.append((score,url,anchor))
            ranked.sort(reverse=True)

            for _, url, _ in ranked[:max_candidates]:
                if article_requests >= max_articles:
                    break
                html = request(session, url, timeout)
                article_requests += 1
                time.sleep(0.35)
                if not html:
                    continue
                text = article_text(html)
                score = score_article(text, match, source)
                if score >= 12:
                    found = {
                        "source":source,
                        "url":url,
                        "score":score,
                        "articleText":text,
                    }
                    break
            if found:
                break

        checked += 1
        if found:
            key = str(match.get("matchNumber") or match.get("id"))
            source = found["source"]
            reports[key] = {
                "title": make_title(match),
                "summary": make_summary(match, source.get("name"), found.get("articleText",""), source),
                "sourceName": source.get("name"),
                "sourceUrl": found["url"],
                "mode": "auto",
                "detectedAt": now_local().isoformat(timespec="seconds"),
                "confidence": found["score"],
            }
            update_retry(state, match, retry_hours, found=True)
            found_count += 1
        else:
            update_retry(state, match, retry_hours, found=False)

    state["lastRunAt"] = now_local().isoformat(timespec="seconds")
    save_json(REPORTS_PATH, reports_doc)
    save_json(STATE_PATH, state)
    print(f"Checked {checked}; found {found_count}; index requests {index_requests}; article requests {article_requests}.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
