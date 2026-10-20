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
| Collector | not started |
| Spot profiles | not started |
| Tide data | source identified, not integrated |
| Scheduled analysis | not started |

## Data sources and attribution

- Forecast data: [Open-Meteo](https://open-meteo.com/) (non-commercial use, CC BY 4.0), wave models including DWD EWAM, ECMWF WAM and Météo-France MFWAM.
- Tides: [Instituto Hidrográfico](https://www.hidrografico.pt/) (to be integrated).

Forecasts are model outputs, not observations. Offshore wave height is not breaking wave height at the beach.
