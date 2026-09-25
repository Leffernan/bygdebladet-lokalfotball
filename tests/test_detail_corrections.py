#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("detail_corrections", ROOT / "scripts" / "detail_corrections.py")
corrections = importlib.util.module_from_spec(spec)
spec.loader.exec_module(corrections)
editorial_spec = importlib.util.spec_from_file_location("editorial_reports", ROOT / "scripts" / "editorial_reports.py")
editorial = importlib.util.module_from_spec(editorial_spec)
editorial_spec.loader.exec_module(editorial)

CONFIG = json.loads((ROOT / "config" / "detail-corrections.json").read_text(encoding="utf-8"))


class CorrectionTests(unittest.TestCase):
    def test_ravn_own_goal_minute_and_narrative(self):
        row = CONFIG["matches"]["23113123026"]
        match = {
            "matchNumber": "23113123026", "age": "G13", "competition": "G13 1. div høst",
            "halfTime": "1–0", **{x: row[x] for x in ("home", "away", "fiksId", "homeScore", "awayScore")},
            "events": [
                {"type": "goal", "team": "home", "player": "Rubin-Augustin Kleiven", "minute": 25},
                {"type": "goal", "team": "home", "player": "Personinfo ikkje tilgjengeleg",
                 "label": "Selvmål", "minute": 49},
                {"type": "goal", "team": "home", "player": "Personinfo ikkje tilgjengeleg",
                 "label": "Spillemål", "minute": 51},
                {"type": "yellow_card", "team": "away", "minute": 43},
            ]
        }
        state = {"matches": {"23113123026": {k: match[k] for k in
                 ("fiksId", "home", "away", "homeScore", "awayScore")}}}
        state["matches"]["23113123026"]["detail"] = {"events": deepcopy(match["events"])}
        document = {"matches": [match]}
        self.assertEqual(corrections.apply_corrections(document, state, CONFIG), 2)
        goals = [e for e in match["events"] if e["type"] == "goal"]
        self.assertEqual([e["minute"] for e in goals], [25, 44, 49, 51])
        self.assertEqual([e["minute"] for e in goals if e.get("ownGoal")], [44])
        self.assertEqual(goals[1]["playerTeam"], "away")
        self.assertEqual(len([e for e in match["events"] if e["type"] == "yellow_card"]), 1)
        self.assertEqual(corrections.apply_corrections(document, state, CONFIG), 0)
        story = editorial.generate(match)
        self.assertTrue(story["completeGoalTimeline"])
        body = " ".join([story["title"], story["lead"], *story["paragraphs"]])
        self.assertIn("sjølvmål frå Brattvåg i det 44. minuttet", body)
        self.assertNotIn("ikkje ei fullstendig målrekkje", body)
        self.assertNotIn("sjølvmål frå Brattvåg i det 49. minuttet", body)

    def test_refuses_wrong_team_or_result(self):
        row = CONFIG["matches"]["23113123026"]
        match = {"matchNumber": "23113123026", **{x: row[x] for x in
                 ("fiksId", "home", "away", "homeScore", "awayScore")}, "events": []}
        match["away"] = "Not Brattvåg"
        with self.assertRaises(ValueError):
            corrections.apply_corrections({"matches": [match]}, {"matches": {}}, CONFIG)

    def test_only_youth_match_ids_with_verified_goal_totals(self):
        self.assertEqual(set(CONFIG["matches"]), {"23113123026", "15149017028"})
        for row in CONFIG["matches"].values():
            self.assertTrue(row["sourceUrl"].startswith("https://www.fotball.no/fotballdata/kamp/"))
            n_home = sum(e["team"] == "home" for e in row["events"])
            n_away = sum(e["team"] == "away" for e in row["events"])
            self.assertEqual((n_home, n_away), (row["homeScore"], row["awayScore"]))


if __name__ == "__main__":
    unittest.main()
