"""Load job fixtures and produce a simple success/fail result."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_fixture(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "watermark_ts" not in data or "rows" not in data:
        raise ValueError("fixture must contain watermark_ts and rows")
    if not isinstance(data["rows"], list):
        raise ValueError("rows must be a list")
    return data


def run_fixture_job(path: Path, partition: str | None = None) -> dict[str, Any]:
    payload = load_fixture(path)
    if partition is None:
        # 正常编排：消费主数据，产出主水位
        return {
            "ok": True,
            "mode": "normal",
            "partition": None,
            "watermark_ts": payload["watermark_ts"],
            "artifact_rows": len(payload["rows"]),
            "sample": payload["rows"][:3],
        }

    # 回补编排：只取该业务日的分区数据，产出分区水位
    partition_data = payload.get("partition_data")
    if not isinstance(partition_data, dict) or partition not in partition_data:
        available = sorted(partition_data.keys()) if isinstance(partition_data, dict) else []
        raise ValueError(
            f"fixture has no data for partition {partition!r}; available: {', '.join(available) or 'none'}"
        )
    part = partition_data[partition]
    if "watermark_ts" not in part or not isinstance(part.get("rows"), list):
        raise ValueError(f"partition {partition!r} must contain watermark_ts and rows")
    return {
        "ok": True,
        "mode": "backfill",
        "partition": partition,
        "watermark_ts": part["watermark_ts"],
        "artifact_rows": len(part["rows"]),
        "sample": part["rows"][:3],
    }
