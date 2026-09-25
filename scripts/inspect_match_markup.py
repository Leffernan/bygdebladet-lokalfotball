#!/usr/bin/env python3
"""Low-traffic NFF markup diagnostics for event parsing (no raw HTML retained)."""
import re
import time
import requests
from bs4 import BeautifulSoup
from detail_parser import _lines, _extract_lineups, _extract_events

URL="https://www.fotball.no/fotballdata/kamp/?fiksId="
for fiks in ("9204245","9201503","9177179"):
    response=requests.get(URL+fiks,headers={"User-Agent":"Mozilla/5.0","Accept":"text/html"},timeout=25)
    response.raise_for_status()
    soup=BeautifulSoup(response.text,"html.parser")
    lines=_lines(soup)
    raw=_extract_events(lines,_extract_lineups(lines))
    print("FIKS",fiks,"status",response.status_code,"lines",len(lines),"events",[(e.get("minute"),e.get("team"),e.get("label"),e.get("ownGoal")) for e in raw],flush=True)
    starts=[i for i,s in enumerate(lines) if re.search(r"selvmål|sjølvmål",s,re.I)]
    print("OWN_GOAL_LABELS",[(i,lines[max(0,i-7):i+8]) for i in starts[:5]],flush=True)
    # Structural profile of the event's nearest HTML container, not the full page.
    for s in soup.find_all(string=re.compile(r"selvmål|sjølvmål",re.I))[:3]:
        parent=s.parent
        profile=[]
        for _ in range(5):
            if not parent: break
            profile.append((parent.name," ".join(parent.get("class",[]))[:90],parent.get_text(" ",strip=True)[:240]))
            parent=parent.parent
        print("ELEMENT",profile,flush=True)
    time.sleep(1.5)
