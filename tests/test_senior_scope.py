"""Keep Vestnes as the local team without dropping division opponents."""
import csv
import gzip
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY = "senior-2026-5-div-menn-romsdal"


class SeniorScopeTest(unittest.TestCase):
    def test_mandalen_is_only_shown_against_vestnes(self):
        with gzip.open(ROOT / "data/fixture_schedule.csv.gz", "rt", encoding="utf-8") as fh:
            fixtures = [r for r in csv.DictReader(fh) if r["competitionKey"] == KEY]
        numbers = {r["matchNumber"] for r in fixtures}
        self.assertTrue(any("Måndalen" in (r["home"], r["away"]) for r in fixtures))
        for row in fixtures:
            side = "home" if row["home"] == "Vestnes Varfjell" else "away" if row["away"] == "Vestnes Varfjell" else ""
            self.assertEqual(row["localTeam"], side)
        for name in ("matches", "upcoming"):
            items = json.loads((ROOT / f"data/{name}.json").read_text(encoding="utf-8"))["matches"]
            self.assertTrue(all("Vestnes Varfjell" in (m["home"], m["away"]) for m in items if m.get("matchNumber") in numbers))
        standings = json.loads((ROOT / "data/competitions.json").read_text(encoding="utf-8"))["competitions"][KEY]["standings"]
        self.assertTrue(any(row["team"] == "Måndalen" for row in standings))

    def test_new_team_logos_exist(self):
        logos = json.loads((ROOT / "data/team-logos.json").read_text(encoding="utf-8"))["logos"]
        for team in ("Fiksdal/Rekdal", "Tomrefjord", "Stordal", "Ravn", "HaNo", "Valldal"):
            self.assertTrue((ROOT / logos[team]).is_file(), team)
        uploaded = {"arendal.png", "bjorset.png", "eide-omegn.png", "eresfjord-vistdal.png",
                    "fk-eik-tonsberg.png", "fiksdal-rekdal.png", "godoy.png", "hano.png",
                    "nordbyen.png", "ravn.png", "rival.png", "sande.png", "sif-hessa.png",
                    "skala.png", "stordal.png", "straumsnes.png", "tingvoll.png",
                    "tomrefjord.png", "valldal.png"}
        self.assertTrue(uploaded <= {Path(path).name for path in logos.values() if path})


if __name__ == "__main__":
    unittest.main()
