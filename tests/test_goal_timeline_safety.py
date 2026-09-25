#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

spec=importlib.util.spec_from_file_location(
    "goal_timeline_safety",
    Path(__file__).resolve().parents[1]/"scripts"/"goal_timeline_safety.py"
)
safety=importlib.util.module_from_spec(spec)
spec.loader.exec_module(safety)


class GoalTimelineSafetyTests(unittest.TestCase):
    def item(self,key="sample",score=(1,1),goals=None):
        goals = goals if goals is not None else [
            {"type":"goal","team":"home","minute":15,"label":"Spillemål"},
            {"type":"goal","team":"away","minute":28,"label":"Spillemål"},
        ]
        match={"matchNumber":key,"homeScore":score[0],"awayScore":score[1],"events":goals}
        state={"matches":{key:{"detail":{"events":goals,"structuredTimeline":True}}}}
        return {"matches":[match]},state

    def test_matching_structured_timeline_is_verified(self):
        m,s=self.item()
        count=safety.apply(m,s,{},{"matches":{}})
        self.assertEqual(count,2)
        self.assertTrue(m["matches"][0]["goalTimelineVerified"])

    def test_audited_contradiction_is_not_published_even_if_old_goals_match(self):
        m,s=self.item()
        safety.apply(m,s,{"matches":{"sample":{"status":"needs_review"}}},{"matches":{}})
        self.assertFalse(m["matches"][0]["goalTimelineVerified"])
        self.assertFalse(s["matches"]["sample"]["goalTimelineVerified"])

    def test_incomplete_goal_timeline_is_suppressed(self):
        m,s=self.item(score=(2,1))
        safety.apply(m,s,{},{"matches":{}})
        self.assertFalse(m["matches"][0]["goalTimelineVerified"])

    def test_manual_correction_requires_matching_score_and_own_goal_team(self):
        goals=[
            {"type":"goal","team":"home","minute":12,"label":"Spillemål"},
            {"type":"goal","team":"home","minute":44,"label":"Sjølvmål","ownGoal":True,"playerTeam":"away"},
        ]
        m,s=self.item(key="corrected",score=(2,0),goals=goals)
        s["matches"]["corrected"]["detail"]["structuredTimeline"]=False
        safety.apply(m,s,{},{"matches":{"corrected":{}}})
        self.assertTrue(m["matches"][0]["goalTimelineVerified"])
        goals[1]["playerTeam"]="home"
        safety.apply(m,s,{},{"matches":{"corrected":{}}})
        self.assertFalse(m["matches"][0]["goalTimelineVerified"])


if __name__=="__main__":
    unittest.main()
