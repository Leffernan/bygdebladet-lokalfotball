#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "detail_parser", Path(__file__).resolve().parents[1] / "scripts" / "detail_parser.py"
)
parser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parser)


class OwnGoalParserTests(unittest.TestCase):
    def test_anonymous_home_own_goal_is_away_goal(self):
        event = parser._goal_event("home", "Personinfo ikkje tilgjengeleg", "Selvmål", unavailable=True)
        self.assertEqual(event["team"], "away")
        self.assertEqual(event["playerTeam"], "home")
        self.assertTrue(event["ownGoal"])
        self.assertTrue(event["personUnavailable"])
        self.assertEqual(event["label"], "Sjølvmål")

    def test_named_away_own_goal_is_home_goal(self):
        event = parser._goal_event("away", "Testspelar", "Sjølvmål")
        self.assertEqual(event["team"], "home")
        self.assertEqual(event["playerTeam"], "away")
        self.assertEqual(event["player"], "Testspelar")

    def test_regular_anonymous_goal_stays_with_scoring_team(self):
        event = parser._goal_event("home", "Personinfo ikkje tilgjengeleg", "Spillemål", unavailable=True)
        self.assertEqual(event["team"], "home")
        self.assertNotIn("ownGoal", event)

    def test_structured_rows_do_not_borrow_neighbouring_minutes_or_labels(self):
        from bs4 import BeautifulSoup
        rows = [
            ("homeTeam", 25, "Rubin-Augustin Kleiven", "Spillemål"),
            ("awayTeam", 44, "Personinfo ikke tilgjengelig", "Selvmål"),
            ("homeTeam", 49, "Personinfo ikke tilgjengelig", "Spillemål"),
            ("homeTeam", 51, "Personinfo ikke tilgjengelig", "Spillemål"),
        ]
        html = '<section class="a_matchTimeline">' + "".join(
            '<div class="timelineEventLine ' + side + '"><div class="timelineEvent">'
            + ('<div class="timelineEventContent"><div>' + person + '</div><div>' + label +
               '</div></div></div><div class="timelineMinute">' + str(minute) + "<span>'</span></div>"
               + '<div class="timelineEvent"></div></div>')
            for side, minute, person, label in rows
        ) + '</section>'
        result = parser.parse_detail(html)
        goals = [e for e in result["events"] if e["type"] == "goal"]
        self.assertTrue(result["structuredTimeline"])
        self.assertEqual([e["minute"] for e in goals], [25, 44, 49, 51])
        self.assertEqual([e.get("ownGoal", False) for e in goals], [False, True, False, False])
        self.assertEqual([e["team"] for e in goals], ["home", "home", "home", "home"])
        self.assertEqual(goals[1]["playerTeam"], "away")

    def test_structured_identical_minute_rows_are_not_deduplicated(self):
        html = '<section class="a_matchTimeline">' + ''.join(
            '<div class="timelineEventLine homeTeam"><div class="timelineEvent">'
            '<div class="timelineEventContent"><div>Personinfo ikke tilgjengelig</div>'
            '<div>Spillemål</div></div></div><div class="timelineMinute">27<span>\'</span>'
            '</div><div class="timelineEvent"></div></div>' for _ in range(2)
        ) + '</section>'
        result = parser.parse_detail(html)
        self.assertEqual(len(result["events"]), 2)

    def test_molde_match_interleaved_column_and_score_reconciliation(self):
        lineups = {
            "home": {"starters": [{"name": "Milla Solskjær"}], "bench": []},
            "away": {"starters": [{"name": "Elvira Anker"}, {"name": "Goda Matulyte"}], "bench": []},
        }
        lines = [
            "26'", "Elvira Anker", "Spillemål",
            "Milla Solskjær", "Spillemål", "35'",
            "37'", "Goda Matulyte", "Advarsel",
            "Personinfo ikke tilgjengelig", "Selvmål", "72'",
        ]
        events = parser._reconcile_goal_events(parser._extract_events(lines, lineups), (1, 2))
        goals = [e for e in events if e["type"] == "goal"]
        self.assertEqual([(e["minute"], e["team"]) for e in goals],
                         [(26, "away"), (35, "home"), (72, "away")])
        self.assertEqual(len([e for e in events if e["type"] == "yellow_card"]), 1)
        self.assertEqual([e for e in goals if e.get("ownGoal")], [{
            "type": "goal", "team": "away", "player": "Personinfo ikkje tilgjengeleg",
            "label": "Sjølvmål", "ownGoal": True, "playerTeam": "home",
            "personUnavailable": True, "minute": 72,
        }])


if __name__ == "__main__":
    unittest.main()
