"""Offline tests for the collector: no network, fake Open-Meteo responses."""

import csv
import json
import sys
import tempfile
import unittest
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "collector"))
import collect  # noqa: E402

TIMES = ["2026-10-21T00:00", "2026-10-21T01:00"]


def fake_fetch(url: str) -> dict:
    query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    model = query["models"][0]
    variables = query["hourly"][0].split(",")
    if model == "broken_model":
        raise collect.FetchError("HTTP 400: Invalid model")
    hourly = {"time": TIMES}
    for i, var in enumerate(variables):
        key = f"{var}_{model}" if model == "suffixed_model" else var
        hourly[key] = [None, None] if var == "sea_level_height_msl" else [1.0 + i, 2.0 + i]
    return {"latitude": 38.625, "longitude": -9.291, "generationtime_ms": 1.2, "hourly": hourly}


class CollectorTest(unittest.TestCase):
    def run_collector(self, marine_models, weather_models, fetch=fake_fetch):
        config = json.loads(collect.CONFIG_PATH.read_text())
        config["marine"]["models"] = marine_models
        config["weather"]["models"] = weather_models
        tmp = Path(tempfile.mkdtemp())
        cfg_path = tmp / "collector.json"
        cfg_path.write_text(json.dumps(config))
        original = collect.CONFIG_PATH
        collect.CONFIG_PATH = cfg_path
        try:
            code = collect.run(fetch=fetch, now=datetime(2026, 10, 20, 22, 0, tzinfo=timezone.utc),
                               data_dir=tmp / "data")
        finally:
            collect.CONFIG_PATH = original
        return code, tmp / "data", config

    def test_partial_failure_keeps_good_models(self):
        code, data, config = self.run_collector(["best_match", "broken_model", "suffixed_model"], ["best_match"])
        self.assertEqual(code, 0)
        manifest = json.loads((data / "latest" / "manifest.json").read_text())
        self.assertEqual(manifest["ok_models"], 3)
        self.assertEqual(manifest["failed_models"], 1)
        broken = next(r for r in manifest["results"] if r["model"] == "broken_model")
        self.assertIn("Invalid model", broken["error"])
        with (data / "latest" / "marine.csv").open() as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 4)  # 2 models x 2 hours
        suffixed = [r for r in rows if r["model"] == "suffixed_model"]
        self.assertEqual(suffixed[0]["wave_height"], "1.0")  # suffix stripped
        ok = next(r for r in manifest["results"] if r["model"] == "best_match" and r["source"] == "marine")
        self.assertEqual(ok["empty_variables"], ["sea_level_height_msl"])
        self.assertTrue((data / "snapshots" / "2026-10-20" / "2026-10-20T2200Z" / "marine_best_match.json").exists())

    def test_whole_source_failure_returns_error(self):
        code, data, _ = self.run_collector(["broken_model"], ["best_match"])
        self.assertEqual(code, 1)
        self.assertFalse((data / "latest" / "marine.csv").exists())
        self.assertTrue((data / "latest" / "weather.csv").exists())
        self.assertTrue((data / "latest" / "manifest.json").exists())

    def test_energy_matches_surf_forecast_scale(self):
        # surf-forecast.com showed 1.8 m / 12 s -> 970 kJ and 0.8 m / 11 s -> 160 kJ.
        # Their H and T are rounded to 0.1 m and 1 s, so allow ~8%.
        self.assertAlmostEqual(collect.wave_energy_kj(1.8, 12), 970, delta=80)
        self.assertAlmostEqual(collect.wave_energy_kj(0.8, 11), 160, delta=13)
        self.assertIsNone(collect.wave_energy_kj(None, 12))
        row = {"swell_wave_height": 1.0, "swell_wave_peak_period": None, "swell_wave_period": 10.0,
               "wave_height": 1.0, "wave_peak_period": 10.0}
        collect.add_derived("marine", row)
        self.assertAlmostEqual(row["energy_swell_kj"], 196, delta=1)  # falls back to mean period
        self.assertAlmostEqual(row["energy_total_kj"], 196, delta=1)

    def test_url_contains_expected_params(self):
        config = json.loads(collect.CONFIG_PATH.read_text())
        url = collect.build_url(config["marine"], "dwd_ewam", 3)
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        self.assertEqual(query["models"], ["dwd_ewam"])
        self.assertEqual(query["timezone"], ["GMT"])
        self.assertEqual(query["cell_selection"], ["sea"])
        self.assertIn("swell_wave_period", query["hourly"][0])


if __name__ == "__main__":
    unittest.main()
