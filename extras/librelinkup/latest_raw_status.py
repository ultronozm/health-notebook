#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_RAW_DIR = Path.home() / "health-notebook/data/raw/librelinkup"
LATEST_RE = re.compile(r"^latest-(\d{8}T\d{6}Z)\.json$")


def parse_pull_timestamp(path: Path) -> datetime | None:
    match = LATEST_RE.match(path.name)
    if not match:
        return None
    return datetime.strptime(match.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)


def newest_latest_file(raw_dir: Path) -> tuple[Path, datetime | None]:
    candidates = sorted(raw_dir.glob("latest-*.json"))
    if not candidates:
        raise SystemExit(f"No latest-*.json files found in {raw_dir}")
    return max(
        ((path, parse_pull_timestamp(path)) for path in candidates),
        key=lambda item: item[1] or datetime.fromtimestamp(item[0].stat().st_mtime, timezone.utc),
    )


def status(raw_dir: Path) -> dict[str, Any]:
    path, pull_time = newest_latest_file(raw_dir)
    data = json.loads(path.read_text())
    now = datetime.now(timezone.utc)
    age_minutes = None
    if pull_time is not None:
        age_minutes = round((now - pull_time).total_seconds() / 60, 1)
    return {
        "raw_dir": str(raw_dir),
        "file_count": len(list(raw_dir.glob("latest-*.json"))),
        "newest_file": str(path),
        "pull_timestamp_utc": pull_time.isoformat() if pull_time else None,
        "pull_age_minutes": age_minutes,
        "measurement_timestamp": data.get("timestamp"),
        "factory_timestamp": data.get("factory_timestamp"),
        "value_mmol_l": data.get("value"),
        "value_mg_dl": data.get("value_in_mg_per_dl"),
        "trend": data.get("trend"),
        "is_low": data.get("is_low"),
        "is_high": data.get("is_high"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Report the newest archived LibreLinkUp latest pull.")
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()

    result = status(args.raw_dir)
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    print(f"raw_dir: {result['raw_dir']}")
    print(f"file_count: {result['file_count']}")
    print(f"newest_file: {result['newest_file']}")
    print(f"pull_timestamp_utc: {result['pull_timestamp_utc']}")
    print(f"pull_age_minutes: {result['pull_age_minutes']}")
    print(f"measurement_timestamp: {result['measurement_timestamp']}")
    print(f"value_mmol_l: {result['value_mmol_l']}")
    print(f"value_mg_dl: {result['value_mg_dl']}")
    print(f"trend: {result['trend']}")
    print(f"is_low: {result['is_low']}")
    print(f"is_high: {result['is_high']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
