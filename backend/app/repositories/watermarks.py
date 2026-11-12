from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import sqlite3


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def list_watermarks(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT w.job_id, j.name AS job_name, w.watermark_ts, w.artifact_rows, w.updated_at
        FROM watermarks w JOIN jobs j ON j.id=w.job_id
        ORDER BY w.job_id
        """
    ).fetchall()
    return [dict(r) for r in rows]


def set_watermark(
    conn: sqlite3.Connection, job_id: int, watermark_ts: str, artifact_rows: int
) -> None:
    conn.execute(
        """
        INSERT INTO watermarks(job_id, watermark_ts, artifact_rows, updated_at)
        VALUES (?,?,?,?)
        ON CONFLICT(job_id) DO UPDATE SET
          watermark_ts=excluded.watermark_ts,
          artifact_rows=excluded.artifact_rows,
          updated_at=excluded.updated_at
        """,
        (job_id, watermark_ts, artifact_rows, _now()),
    )


def list_partition_watermarks(
    conn: sqlite3.Connection, partition: str | None = None
) -> list[dict[str, Any]]:
    if partition is None:
        rows = conn.execute(
            """
            SELECT pw.job_id, j.name AS job_name, pw.partition,
                   pw.watermark_ts, pw.artifact_rows, pw.updated_at
            FROM partition_watermarks pw JOIN jobs j ON j.id=pw.job_id
            ORDER BY pw.partition DESC, pw.job_id
            """
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT pw.job_id, j.name AS job_name, pw.partition,
                   pw.watermark_ts, pw.artifact_rows, pw.updated_at
            FROM partition_watermarks pw JOIN jobs j ON j.id=pw.job_id
            WHERE pw.partition=?
            ORDER BY pw.job_id
            """,
            (partition,),
        ).fetchall()
    return [dict(r) for r in rows]


def set_partition_watermark(
    conn: sqlite3.Connection,
    *,
    job_id: int,
    partition: str,
    watermark_ts: str,
    artifact_rows: int,
) -> None:
    conn.execute(
        """
        INSERT INTO partition_watermarks(job_id, partition, watermark_ts, artifact_rows, updated_at)
        VALUES (?,?,?,?,?)
        ON CONFLICT(job_id, partition) DO UPDATE SET
          watermark_ts=excluded.watermark_ts,
          artifact_rows=excluded.artifact_rows,
          updated_at=excluded.updated_at
        """,
        (job_id, partition, watermark_ts, artifact_rows, _now()),
    )


def count_watermarked_partitions(conn: sqlite3.Connection, partition: str | None = None) -> int:
    if partition is None:
        row = conn.execute(
            "SELECT COUNT(*) c FROM partition_watermarks WHERE watermark_ts IS NOT NULL"
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(*) c FROM partition_watermarks WHERE watermark_ts IS NOT NULL AND partition=?",
            (partition,),
        ).fetchone()
    return int(row["c"])
