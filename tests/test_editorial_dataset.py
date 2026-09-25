#!/usr/bin/env python3
"""Check all generated stories for chronology regressions."""
from __future__ import annotations

import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("editorial_reports", ROOT / "scripts" / "editorial_reports.py")
editorial = importlib.util.module_from_spec(spec)
spec.loader.exec_module(editorial)


def mentioned_minutes(paragraph):
    found = []
    for m in re.finditer(r"i det (\d+)\. minuttet|i minutta ([\d,\sog]+)\.", paragraph):
        if m.group(1):
            found.append(int(m.group(1)))
        else:
            found.extend(int(x) for x in re.findall(r"\d+", m.group(2)))
    return found


class PublishedNarrativesTest(unittest.TestCase):
    def test_every_complete_story_follows_goal_order(self):
        doc = json.loads((ROOT / "data" / "matches.json").read_text(encoding="utf-8"))
        self.assertTrue(doc["matches"])
        for match in doc["matches"]:
            with self.subTest(match=match.get("matchNumber")):
                story = editorial.generate(match)
                self.assertIsNotNone(story)
                goals, complete, ordered = editorial.goal_data(match)
                if match.get("goalTimelineVerified") is False or not ordered:
                    continue
                minutes = [minute for p in story["paragraphs"] for minute in mentioned_minutes(p)]
                self.assertEqual(minutes, [event["minute"] for event in ordered])
                self.assertNotIn("stod for det første målet", " ".join(story["paragraphs"]))
                self.assertFalse(any(p.startswith("Etter pause fekk") for p in story["paragraphs"]))
                pause = [i for i, p in enumerate(story["paragraphs"]) if p.startswith("Til pause stod det")]
                boundary = editorial.half_time_split(
                    ordered, editorial.safe_half(match), editorial.age_duration(match)
                )
                self.assertEqual(len(pause), 1 if boundary is not None else 0)
                if pause:
                    before_pause = [
                        minute for p in story["paragraphs"][:pause[0]]
                        for minute in mentioned_minutes(p)
                    ]
                    self.assertEqual(before_pause, [e["minute"] for e in ordered[:boundary]])


if __name__ == "__main__":
    unittest.main()
