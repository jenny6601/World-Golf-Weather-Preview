#!/usr/bin/env python3
"""Fetch provider-native 6-hourly Open-Meteo seasonal data for golf courses."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

API = "https://seasonal-api.open-meteo.com/v1/seasonal"
MODELS = ("ecmwf_ec46", "ecmwf_seas5")
HOURLY = "precipitation,temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,wind_direction_10m,wind_gusts_10m,weather_code"
USER_AGENT = "World-Golf-Weather-Preview/90day-data-pipeline"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def validate_course(course: dict) -> None:
    required = ("course_id", "course_name", "country_code", "latitude", "longitude", "timezone")
    for key in required:
        if key not in course or course[key] in (None, ""):
            raise ValueError(f"course missing required field: {key}")
    lat, lon = float(course["latitude"]), float(course["longitude"])
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(f"invalid coordinates for {course['course_id']}")
    if not re.fullmatch(r"[A-Z]{2}", str(course["country_code"])):
        raise ValueError(f"country_code must be ISO alpha-2: {course['course_id']}")
    try:
        ZoneInfo(str(course["timezone"]))
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"invalid IANA timezone for {course['course_id']}: {course['timezone']}") from exc


def fetch_model(course: dict, model: str, timeout: int = 45) -> dict:
    params = {
        "latitude": course["latitude"],
        "longitude": course["longitude"],
        "hourly": HOURLY,
        "models": model,
        "forecast_days": 46 if model == "ecmwf_ec46" else 90,
        "timezone": course["timezone"],
        "timeformat": "iso8601",
        "precipitation_unit": "mm",
        "wind_speed_unit": "kmh",
        "temperature_unit": "celsius",
    }
    url = API + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    retrieved_at = utc_now()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read()
        status = response.status
    payload = json.loads(body.decode("utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("hourly"), dict):
        raise ValueError(f"unexpected {model} response: hourly data missing")
    times = payload["hourly"].get("time", [])
    if not times:
        raise ValueError(f"empty time axis for {model}")
    return {
        "schema_version": "1.0.0",
        "source_id": "open_meteo_ecmwf_extended" if model == "ecmwf_ec46" else "open_meteo_ecmwf_seas5",
        "provider": "Open-Meteo",
        "model": model,
        "native_temporal_resolution": "6-hourly",
        "location": {
            "course_id": course["course_id"],
            "course_name": course["course_name"],
            "country_code": course["country_code"],
            "latitude": float(course["latitude"]),
            "longitude": float(course["longitude"]),
            "timezone": course["timezone"],
            "verification_status": course.get("verification_status", "unverified"),
            "coordinate_source": course.get("coordinate_source"),
            "grid_elevation_m": payload.get("elevation"),
        },
        "retrieved_at": retrieved_at,
        "provider_generationtime_ms": payload.get("generationtime_ms"),
        "provider_timezone": payload.get("timezone"),
        "provider_utc_offset_seconds": payload.get("utc_offset_seconds"),
        "valid_time_start": times[0],
        "valid_time_end": times[-1],
        "valid_time_count": len(times),
        "http_status": status,
        "api_endpoint": API,
        "request_parameters": params,
        "provider_payload": payload,
        "semantic_guardrails": [
            "此檔保存供應商原始 6 小時資料；不得將 6 小時資料解讀為每小時實測。",
            "EC46 與 SEAS5 分開保存，不將兩個模式直接混合。",
            "只有供應商明確提供的 precipitation_probability 才可標示為降雨機率；本次欄位不包含該變數。",
            "週／月異常值不得解讀為單日降雨機率。",
            "retrieved_at 是系統擷取時間，不代表模式初始化或發布時間。",
            "verification_status 原樣保留；partially_verified 不得升格為 verified。",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--courses", required=True, help="JSON file containing course coordinates")
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
        "source_master": config.get("source_path") or config.get("source_repository"),
        "course_count": len(courses),
        "verification_counts": config.get("counts", {}),
        "records": [],
        "errors": [],
        "notes": ["原始 6 小時資料快照；不產生日期排名或逐日降雨機率。"],
    }
    for course in courses:
        try:
            validate_course(course)
        except Exception as exc:
            manifest["errors"].append({"course_id": course.get("course_id"), "error": str(exc)})
            continue
        for model in MODELS:
            try:
                record = fetch_model(course, model)
                stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", course["course_id"])
                filename = f"{safe_id}_{model}_{stamp}.json"
                (outdir / filename).write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
                manifest["records"].append({
                    "course_id": course["course_id"], "model": model, "file": filename,
                    "retrieved_at": record["retrieved_at"], "valid_time_count": record["valid_time_count"],
                    "verification_status": course.get("verification_status", "unverified"), "status": "valid"
                })
            except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
                manifest["errors"].append({"course_id": course["course_id"], "model": model, "error": str(exc)})
            time.sleep(max(0.0, args.pause))
    if manifest["errors"]:
        manifest["status"] = "partial" if manifest["records"] else "failed"
    if not courses:
        manifest["status"] = "no_targets_configured"
        manifest["notes"].append("球場清單為空，本次不呼叫 API。")
    manifest["run_finished_at"] = utc_now()
    (outdir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in ("status", "course_count", "records", "errors")}, ensure_ascii=False, indent=2))
    return 1 if manifest["status"] in ("failed", "partial") else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
