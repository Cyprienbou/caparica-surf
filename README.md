# caparica-surf

Personal surf forecasting agent for Costa da Caparica, Portugal.

Goal: find clean, manageable sessions (breaking waves ~0.7 to 1.5 m, light offshore or cross-offshore wind) and get a notification 12 to 24 hours in advance.

## Architecture (planned)

1. **Collector** (GitHub Actions, Python): pulls hourly wave, swell and wind forecasts from the Open-Meteo Marine and Forecast APIs, from at least two models, and stores timestamped snapshots in `data/`.
2. **Reference data**: spot profiles (orientation, favourable wind, tide preferences, hazards) and tide predictions from Instituto Hidrográfico tables.
3. **Analysis agent** (scheduled Claude task): reads the latest snapshots, scores each spot and time window out of 100, and sends a GO / CONDITIONAL / NO-GO notification.
4. **History**: alert log to avoid duplicates and compare forecasts over time.

## Status

| Component | State |
|---|---|
| Repository | created |
| Collector | written, offline tests passing, first live run pending |
| Spot profiles | not started |
| Tide data | source identified, not integrated |
| Scheduled analysis | not started |

## Collector

`collector/collect.py` (standard library only) requests each wave model and each wind model separately, so one unavailable model never breaks a run. Points and models live in `config/collector.json`.

Outputs, all timestamps in UTC:

- `data/latest/marine.csv` and `data/latest/weather.csv`: one row per model and hour
- `data/latest/manifest.json`: run time, grid cell actually used, per-model status and errors
- `data/snapshots/<date>/<run_id>/`: raw API responses, kept to compare forecasts over time

`.github/workflows/collect.yml` runs it six times a day (two UTC hours per Lisbon slot, to cover daylight saving time) and on demand. Tests: `python3 -m unittest discover -s tests`.

## Data sources and attribution

- Forecast data: [Open-Meteo](https://open-meteo.com/) (non-commercial use, CC BY 4.0), wave models including DWD EWAM, ECMWF WAM and Météo-France MFWAM.
- Tides: [Instituto Hidrográfico](https://www.hidrografico.pt/) (to be integrated).

Forecasts are model outputs, not observations. Offshore wave height is not breaking wave height at the beach.
