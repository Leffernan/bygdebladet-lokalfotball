#!/usr/bin/env python3
from __future__ import annotations
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "editorial_reports",
    Path(__file__).resolve().parents[1] / "scripts" / "editorial_reports.py"
)
editorial = importlib.util.module_from_spec(spec)
spec.loader.exec_module(editorial)


def match(h, a, goals=None, age="G13", half=None):
    return {
        "home": "Heimelaget", "away": "Bortelaget", "homeScore": h,
        "awayScore": a, "age": age, "competition": f"{age} 1. divisjon",
        "halfTime": half, "events": goals or [], "matchNumber": "test"
    }


def goal(minute, side, name, **more):
    return {"minute": minute, "team": side, "type": "goal", "player": name, **more}


class EditorialTests(unittest.TestCase):
    def test_all_three_goals_named(self):
        m = match(3, 0, [goal(10, "home", "Test Spelar"), goal(26, "home", "Test Spelar"), goal(62, "home", "Test Spelar")])
        story = editorial.generate(m)
        self.assertIn("Test Spelar herja", story["title"])
        self.assertIn("alle dei tre måla", story["lead"])
        self.assertTrue(story["completeGoalTimeline"])

    def test_late_winner(self):
        m = match(2, 1, [goal(10, "home", "A"), goal(34, "away", "B"), goal(69, "home", "C")])
        s = editorial.generate(m)
        self.assertIn("C avgjorde seint", s["title"])
        self.assertIn("69.", s["lead"])

    def test_not_a_late_winner_if_goal_only_extends_lead(self):
        m = match(2, 0, [goal(12, "home", "A"), goal(69, "home", "B")])
        s = editorial.generate(m)
        self.assertNotIn("avgjorde seint", s["title"])
        self.assertNotIn("Vinnarmålet kom", s["lead"])

    def test_comeback(self):
        m = match(2, 1, [goal(12, "away", "B"), goal(33, "home", "A"), goal(49, "home", "C")])
        self.assertIn("snudde", editorial.generate(m)["title"])

    def test_missing_goals_no_invented_scorer(self):
        m = match(3, 0, [goal(8, "home", "A")])
        s = editorial.generate(m)
        self.assertNotIn("hattrick", (s["title"]+" ".join(s["paragraphs"])).lower())
        self.assertFalse(s["completeGoalTimeline"])
        self.assertIn("ikkje ei fullstendig", " ".join(s["paragraphs"]))

    def test_anonymous_still_counted(self):
        m = match(3, 0, [
            goal(10, "home", "A"),
            goal(25, "home", "Personinfo ikkje tilgjengeleg", personUnavailable=True),
            goal(58, "home", "A"),
        ])
        s = editorial.generate(m)
        self.assertTrue(s["completeGoalTimeline"])
        self.assertNotIn("alle dei tre", s["lead"])
        self.assertNotIn("Personinfo", s["title"])

    def test_zero_minute_blocks_chronology(self):
        m = match(1, 1, [goal(0, "home", "A"), goal(0, "away", "B")])
        s = editorial.generate(m)
        self.assertFalse(any("første målet" in p for p in s["paragraphs"]))

    def test_opposite_goals_same_minute_blocks_chronology(self):
        m = match(2, 1, [goal(12, "home", "A"), goal(69, "away", "B"), goal(69, "home", "C")])
        self.assertNotIn("avgjorde seint", editorial.generate(m)["title"])

    def test_goalless_match_and_senior_exclusion(self):
        self.assertIn("Mållaus", editorial.generate(match(0, 0))["title"])
        self.assertIsNone(editorial.generate(match(3, 0, age="MENN")))

    def test_half_time_must_not_exceed_final(self):
        m = match(2, 1, half="4–0")
        self.assertNotIn("Til pause", " ".join(editorial.generate(m)["paragraphs"]))

    def test_no_unauthorised_tactical_claim(self):
        m = match(7, 0)
        text = " ".join(editorial.generate(m).values().__str__().split()).lower()
        self.assertNotIn("dominerte", text)
        self.assertNotIn("sjansar", text)


if __name__ == "__main__":
    unittest.main()
