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

    def test_anonymous_late_own_goal_decides_molde_match(self):
        m = match(1, 2, [
            goal(26, "away", "Elvira Anker"),
            goal(35, "home", "Milla Solskjær"),
            goal(72, "away", "Personinfo ikkje tilgjengeleg",
                 label="Sjølvmål", ownGoal=True, playerTeam="home",
                 personUnavailable=True),
        ], age="J14", half="1–1")
        m["home"] = "Vestnes Varfjell"
        m["away"] = "Molde 2"
        story = editorial.generate(m)
        text = " ".join([story["title"], story["lead"], *story["paragraphs"]])
        self.assertTrue(story["completeGoalTimeline"])
        self.assertIn("sjølvmål", text.casefold())
        self.assertIn("Vestnes Varfjell", story["lead"])
        self.assertIn("72.", text)
        self.assertNotIn("ikkje ei fullstendig målrekkje", text)
        self.assertNotIn("Personinfo", text)
        self.assertIn("sjølvmål", story["title"].casefold())

    def test_own_goal_is_not_counted_as_player_scorer(self):
        m = match(0, 3, [
            goal(10, "away", "A"),
            goal(21, "away", "A"),
            goal(42, "away", "Personinfo ikkje tilgjengeleg",
                 label="Selvmål", ownGoal=True, playerTeam="home",
                 personUnavailable=True),
        ])
        story = editorial.generate(m)
        self.assertNotIn("alle dei tre", story["lead"])
        self.assertIn("sjølvmål", " ".join(story["paragraphs"]).casefold())

    def test_non_decisive_own_goal_is_still_mentioned(self):
        m = match(1, 3, [
            goal(12, "away", "A"),
            goal(20, "away", "Personinfo ikkje tilgjengeleg",
                 label="Selvmål", ownGoal=True, playerTeam="home",
                 personUnavailable=True),
            goal(32, "home", "B"),
            goal(58, "away", "A"),
        ])
        story = editorial.generate(m)
        self.assertIn("sjølvmål", " ".join(story["paragraphs"]).casefold())

    def test_disputed_timeline_does_not_invent_scorers_or_match_sequence(self):
        m = match(0, 7, [
            goal(4, "away", "A"), goal(16, "away", "A"),
            goal(31, "away", "A"), goal(34, "away", "B"),
            goal(49, "away", "B"), goal(53, "away", "C"), goal(56, "away", "C"),
        ], half="0–4")
        m["goalTimelineVerified"] = False
        s = editorial.generate(m)
        body = " ".join([s["title"], s["lead"], *s["paragraphs"]])
        self.assertNotIn("Hattrick", body)
        self.assertNotIn("stod for det første målet", body)
        self.assertIn("ikkje stadfesta", body)
        self.assertFalse(s["completeGoalTimeline"])

    def test_ravn_report_is_chronological_and_has_no_obvious_1_0(self):
        m = match(4, 0, [
            goal(25, "home", "Rubin-Augustin Kleiven"),
            goal(44, "home", "Personinfo ikkje tilgjengeleg",
                 ownGoal=True, playerTeam="away", label="Sjølvmål",
                 personUnavailable=True),
            goal(49, "home", "Personinfo ikkje tilgjengeleg",
                 personUnavailable=True),
            goal(51, "home", "Personinfo ikkje tilgjengeleg",
                 personUnavailable=True),
        ], half="1–0")
        m.update(home="Ravn/Norborg", away="Brattvåg")
        story = editorial.generate(m)
        self.assertEqual(story["paragraphs"], [
            "Rubin-Augustin Kleiven gav Ravn/Norborg leiinga i det 25. minuttet.",
            "Til pause stod det 1–0.",
            "Eit sjølvmål frå Brattvåg i det 44. minuttet auka leiinga til 2–0 for Ravn/Norborg.",
            "Ravn/Norborg auka leiinga med mål i minutta 49 og 51.",
        ])
        self.assertFalse(any("Etter pause fekk" in p for p in story["paragraphs"]))
        self.assertNotIn("det første målet", " ".join(story["paragraphs"]))

    def test_molde_equaliser_before_halftime_own_goal_after(self):
        m = match(1, 2, [
            goal(26, "away", "Elvira Anker"),
            goal(35, "home", "Milla Solskjær"),
            goal(72, "away", "Personinfo ikkje tilgjengeleg",
                 ownGoal=True, playerTeam="home", label="Sjølvmål",
                 personUnavailable=True),
        ], age="J14", half="1–1")
        m.update(home="Vestnes Varfjell", away="Molde 2")
        s = editorial.generate(m)
        self.assertIn("Elvira Anker", s["paragraphs"][0])
        self.assertIn("Milla Solskjær", s["paragraphs"][1])
        self.assertEqual(s["paragraphs"][2], "Til pause stod det 1–1.")
        self.assertIn("72.", s["paragraphs"][3])

    def test_no_halftime_inserted_at_impossible_goal_minute(self):
        m = match(1, 1, [
            goal(46, "home", "A"), goal(49, "away", "B"),
        ], half="1–1")
        s = editorial.generate(m)
        self.assertFalse(any("Til pause" in p for p in s["paragraphs"]))

    def test_missing_timeline_still_reports_official_pause_result(self):
        m = match(3, 0, [goal(8, "home", "A")], half="1–0")
        s = editorial.generate(m)
        self.assertIn("Til pause stod det 1–0.", s["paragraphs"])
        self.assertIn("ikkje ei fullstendig", " ".join(s["paragraphs"]))

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
