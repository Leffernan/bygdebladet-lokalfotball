#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path

from detail_parser import parse_detail

here = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("source_sync_base", here / "source_sync.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.parse_detail = parse_detail
base.DETAIL_PARSER_VERSION = 3

if __name__ == "__main__":
    raise SystemExit(base.main())
