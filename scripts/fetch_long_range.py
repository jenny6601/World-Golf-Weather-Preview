#!/usr/bin/env python3
"""Fetch raw Open-Meteo seasonal forecast payloads for configured golf courses.

This stage deliberately preserves provider-native payloads and does not derive
daily rain probabilities from seasonal anomalies or downsample weekly/monthly data.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://seasonal-api.open-meteo.com/v1/seasonal"
MODELS = ("ecmwf_ec46", "ecmwf_seas5")
HOURLY = "precipitation,temperature_2m,wind_speed_10m,wind_direction_10m"
USER_AGENT = "World-Golf-Weather-Preview/90day-data-pipeline"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def validate_course(course: dict) -> None:
    for key in ("course_id", "course_name", "country_code", "latitude", "longitude"):
        if key not in course:
            raise ValueError(f"course missing required field: {key}")
    lat, lon = float(course["latitude"]), float(course["longitude"])
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(f"invalid coordinates for {course['course_id']}")
    if len(str(course["country_code"])) != 2:
        raise ValueError(f"country_code must be ISO alpha-2: {course['course_id']}")


def fetch_model(course: dict, model: str, timeout: int = 45) -> dict:
    params = {
        "latitude": course["latitude"],
        "longitude": course["longitude"],
        "hourly": HOURLY,
        "models": model,
        "forecast_days": 46 if model == "ecmwf_ec46" else 90,
        "timezone": "UTC",
        "timeformat": "iso8601",
        "precipitation_unit": "mm",
        "wind_speed_unit": "kmh",
    }
    url = API + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    retrieved_at = utc_now()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read()
        status = response.status
    payload = json.loads(body.decode("utf-8"))
    if not isinstance(payload, dict) or "hourly" not in payload:
        raise ValueError(f"unexpected {model} response: hourly data missing")
    return {
        "schema_version": "1.0.0",
        "source_id": "open_meteo_ecmwf_extended" if model == "ecmwf_ec46" else "open_meteo_ecmwf_seas5",
        "provider": "Open-Meteo",
        "model": model,
        "location": {
            "course_id": course["course_id"],
            "course_name": course["course_name"],
            "country_code": course["country_code"],
            "latitude": float(course["latitude"]),
            "longitude": float(course["longitude"]),
            "timezone": payload.get("timezone", "UTC"),
            "grid_elevation_m": payload.get("elevation"),
        },
        "retrieved_at": retrieved_at,
        "provider_generationtime_ms": payload.get("generationtime_ms"),
        "http_status": status,
        "api_endpoint": API,
        "request_parameters": params,
        "provider_payload": payload,
        "semantic_guardrails": [
            "此檔保存供應商原始回應；不得將週／月異常值解讀為單日降雨機率。",
            "EC46 僅保留供應商實際回傳的預報時段；不得補齊缺少日期。",
            "SEAS5 的可用時間尺度依原始回應為準，不得將季節資料偽裝成逐日預報。",
            "retrieved_at 是系統擷取時間，不代表模式初始化或發布時間。",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--courses", required=True, help="JSON file containing verified course coordinates")
    parser.add_argument("--output", required=True, help="Output directory for raw JSON snapshots")
    parser.add_argument("--pause", type=float, default=1.0, help="Seconds between API requests")
    args = parser.parse_args()

    config = json.loads(pathlib.Path(args.courses).read_text(encoding="utf-8"))
    courses = config.get("courses", [])
    if not isinstance(courses, list):
        raise ValueError("courses must be a JSON array")
    outdir = pathlib.Path(args.output)
    outdir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": "1.0.0",
        "run_started_at": utc_now(),
        "status": "success",
        "course_count": len(courses),
        "records": [],
        "errors": [],
        "notes": ["原始資料快照；不產生日期排名或逐日降雨機率。"],
    }
    for course in courses:
        try:
            validate_course(course)
        except Exception as exc:
            manifest["errors"].append({"course": course, "error": str(exc)})
            continue
        for model in MODELS:
            try:
                record = fetch_model(course, model)
                stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in course["course_id"])
                filename = f"{safe_id}_{model}_{stamp}.json"
                (outdir / filename).write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                manifest["records"].append({"course_id": course["course_id"], "model": model, "file": filename, "retrieved_at": record["retrieved_at"], "status": "valid"})
            except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
                manifest["errors"].append({"course_id": course["course_id"], "model": model, "error": str(exc)})
            time.sleep(max(0.0, args.pause))
    if manifest["errors"]:
        manifest["status"] = "partial" if manifest["records"] else "failed"
    if not courses:
        manifest["status"] = "no_targets_configured"
        manifest["notes"].append("尚未匯入已核實的全球球場座標，因此本次不呼叫 API。")
    manifest["run_finished_at"] = utc_now()
    (outdir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in ("status", "course_count", "records", "errors")}, ensure_ascii=False, indent=2))
    return 1 if manifest["status"] in ("failed", "partial") else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
