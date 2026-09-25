#!/usr/bin/env python3
from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

from detail_parser import parse_detail

here = Path(__file__).resolve().parent
root = here.parent

def remove_senior_fixtures():
    path = root / "data" / "fixtures.csv"
    if not path.exists():
        return
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    def senior(row):
        values = [str(v or "").strip().casefold() for v in row.values()]
        return (
            "menn" in values
            or "kvinner" in values
            or "5-div-menn" in values
            or any("5.div menn" in v or "5. div menn" in v for v in values)
        )

    filtered = [row for row in rows if not senior(row)]
    if len(filtered) == len(rows):
        return

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(filtered)

remove_senior_fixtures()

spec = importlib.util.spec_from_file_location("source_sync_base", here / "source_sync.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.parse_detail = parse_detail
base.DETAIL_PARSER_VERSION = 4

if __name__ == "__main__":
    raise SystemExit(base.main())
