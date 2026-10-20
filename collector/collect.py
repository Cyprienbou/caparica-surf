"""Collect hourly wave and wind forecasts for Costa da Caparica from Open-Meteo.

Each model is requested separately so that one invalid or unavailable model
never breaks the whole run. Every run writes:

- data/snapshots/<YYYY-MM-DD>/<run_id>/<source>_<model>.json  raw API responses
- data/latest/<source>.csv                                    tidy wide table (one row per model and hour, UTC)
- data/latest/manifest.json                                   run metadata, per-model status and errors

Only the Python standard library is used.
"""

from __future__ import annotations

import csv
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "collector.json"
DATA_DIR = ROOT / "data"
USER_AGENT = "caparica-surf/0.1 (personal non-commercial surf forecast; github.com/Cyprienbou/caparica-surf)"
ATTRIBUTION = "Weather and marine data by Open-Meteo.com (CC BY 4.0); wave models from DWD, ECMWF, Meteo-France and NOAA."

Fetcher = Callable[[str], dict]


class FetchError(Exception):
    pass


def http_get_json(url: str, retries: int = 3, timeout: int = 30) -> dict:
    """GET a JSON document, retrying on network errors and 5xx/429 responses."""
    last_error = ""
    for attempt in range(1, retries + 1):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                reason = json.loads(body).get("reason", body)
            except json.JSONDecodeError:
                reason = body[:300]
            last_error = f"HTTP {exc.code}: {reason}"
            if exc.code < 500 and exc.code != 429:
                break  # client error, retrying will not help
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        if attempt < retries:
            time.sleep(5 * attempt)
    raise FetchError(last_error)


def build_url(source_cfg: dict, model: str, forecast_days: int) -> str:
    params = {
        "latitude": source_cfg["point"]["latitude"],
        "longitude": source_cfg["point"]["longitude"],
        "hourly": ",".join(source_cfg["hourly"]),
        "models": model,
        "forecast_days": forecast_days,
        "timezone": "GMT",
        "timeformat": "iso8601",
    }
    params.update(source_cfg.get("extra_params", {}))
    return f"{source_cfg['endpoint']}?{urllib.parse.urlencode(params)}"


def normalise_hourly(payload: dict, model: str, variables: list[str]) -> dict[str, list]:
    """Return {variable: values} with model suffixes stripped, plus the time axis."""
    hourly = payload.get("hourly", {})
    out = {"time": hourly.get("time", [])}
    for var in variables:
        values = hourly.get(var)
        if values is None:
            values = hourly.get(f"{var}_{model}")
        out[var] = values if values is not None else [None] * len(out["time"])
    return out


def collect_source(source: str, source_cfg: dict, forecast_days: int, run_dir: Path,
                   fetch: Fetcher) -> tuple[list[dict], list[dict]]:
    """Fetch every model for one source. Returns (rows for the CSV, per-model status)."""
    rows: list[dict] = []
    statuses: list[dict] = []
    variables = source_cfg["hourly"]
    for model in source_cfg["models"]:
        url = build_url(source_cfg, model, forecast_days)
        status = {"source": source, "model": model, "url": url, "ok": False}
        try:
            payload = fetch(url)
            if payload.get("error"):
                raise FetchError(payload.get("reason", "unknown API error"))
        except FetchError as exc:
            status["error"] = str(exc)
            statuses.append(status)
            print(f"[{source}/{model}] FAILED: {exc}", file=sys.stderr)
            continue

        (run_dir / f"{source}_{model}.json").write_text(json.dumps(payload, separators=(",", ":")))
        hourly = normalise_hourly(payload, model, variables)
        n_hours = len(hourly["time"])
        empty_vars = [v for v in variables if all(x is None for x in hourly[v])]
        for i, t in enumerate(hourly["time"]):
            row = {"model": model, "time_utc": t}
            row.update({v: hourly[v][i] for v in variables})
            rows.append(row)

        status.update({
            "ok": True,
            "grid_latitude": payload.get("latitude"),
            "grid_longitude": payload.get("longitude"),
            "generationtime_ms": payload.get("generationtime_ms"),
            "hours": n_hours,
            "first_time_utc": hourly["time"][0] if n_hours else None,
            "last_time_utc": hourly["time"][-1] if n_hours else None,
            "empty_variables": empty_vars,
        })
        statuses.append(status)
        print(f"[{source}/{model}] ok: {n_hours} hours, grid ({status['grid_latitude']}, "
              f"{status['grid_longitude']}), empty vars: {empty_vars or 'none'}")
    return rows, statuses


def write_csv(path: Path, rows: list[dict], variables: list[str]) -> None:
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["model", "time_utc", *variables])
        writer.writeheader()
        writer.writerows(rows)


def run(fetch: Fetcher = http_get_json, now: datetime | None = None, data_dir: Path = DATA_DIR) -> int:
    config = json.loads(CONFIG_PATH.read_text())
    now = now or datetime.now(timezone.utc)
    run_id = now.strftime("%Y-%m-%dT%H%MZ")
    run_dir = data_dir / "snapshots" / now.strftime("%Y-%m-%d") / run_id
    latest_dir = data_dir / "latest"
    run_dir.mkdir(parents=True, exist_ok=True)
    latest_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "run_id": run_id,
        "run_at_utc": now.isoformat(timespec="seconds"),
        "attribution": ATTRIBUTION,
        "note": "Forecast model output, not observations. Offshore wave height is not breaking wave height.",
        "points": {s: config[s]["point"] for s in ("marine", "weather")},
        "results": [],
    }
    exit_code = 0
    for source in ("marine", "weather"):
        rows, statuses = collect_source(source, config[source], config["forecast_days"], run_dir, fetch)
        manifest["results"].extend(statuses)
        if rows:
            write_csv(latest_dir / f"{source}.csv", rows, config[source]["hourly"])
        else:
            print(f"[{source}] every model failed; latest/{source}.csv left unchanged", file=sys.stderr)
            exit_code = 1

    manifest["ok_models"] = sum(r["ok"] for r in manifest["results"])
    manifest["failed_models"] = len(manifest["results"]) - manifest["ok_models"]
    manifest_text = json.dumps(manifest, indent=2)
    # Always publish the manifest so the analysis step can see failures and stale CSVs.
    (run_dir / "manifest.json").write_text(manifest_text)
    (latest_dir / "manifest.json").write_text(manifest_text)
    print(f"Run {run_id}: {manifest['ok_models']} models ok, {manifest['failed_models']} failed")
    return exit_code


if __name__ == "__main__":
    sys.exit(run())
