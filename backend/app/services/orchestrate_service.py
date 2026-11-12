from __future__ import annotations

from typing import Any

from app.config import FIXTURES_DIR
from app.db import connect
from app.engines.dependency import ready_by_upstream_success, topological_layers
from app.engines.job_runner import run_fixture_job
from app.repositories import jobs as jobs_repo
from app.repositories import orchestrations as orch_repo
from app.repositories import watermarks as wm_repo


def dashboard_stats() -> dict[str, Any]:
    conn = connect()
    try:
        return {
            "job_count": conn.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"],
            "enabled_jobs": conn.execute(
                "SELECT COUNT(*) c FROM jobs WHERE enabled=1"
            ).fetchone()["c"],
            "orchestration_count": conn.execute(
                "SELECT COUNT(*) c FROM orchestrations"
            ).fetchone()["c"],
            "attempt_count": conn.execute(
                "SELECT COUNT(*) c FROM job_attempts"
            ).fetchone()["c"],
            "watermarked_jobs": conn.execute(
                "SELECT COUNT(*) c FROM watermarks WHERE watermark_ts IS NOT NULL"
            ).fetchone()["c"],
            "partition_watermark_rows": wm_repo.count_watermarked_partitions(conn),
        }
    finally:
        conn.close()


def run_orchestration(partition: str | None = None) -> dict[str, Any]:
    # 分区标识（如业务日）存在即回补模式：只写分区水位，不抬主水位
    mode = "backfill" if partition else "normal"
    conn = connect()
    try:
        jobs = [j for j in jobs_repo.list_jobs(conn) if j["enabled"]]
        orch_id = orch_repo.create_orchestration(conn, mode=mode, partition=partition)
        success_names: set[str] = set()
        layers = topological_layers(jobs)

        for layer in layers:
            for job in layer:
                ready, reason = ready_by_upstream_success(job["depends_on"], success_names)
                if not ready:
                    orch_repo.insert_attempt(
                        conn,
                        orchestration_id=orch_id,
                        job_id=job["id"],
                        attempt_no=1,
                        status="skipped_dep",
                        detail={"mode": mode, "partition": partition, "reason": reason},
                    )
                    continue
                try:
                    result = run_fixture_job(FIXTURES_DIR / job["fixture_path"], partition)
                    orch_repo.insert_attempt(
                        conn,
                        orchestration_id=orch_id,
                        job_id=job["id"],
                        attempt_no=1,
                        status="success",
                        detail=result,
                    )
                    if mode == "backfill":
                        # 回补：写入 (作业, 分区) 维度的分区水位，主水位保持不动
                        wm_repo.set_partition_watermark(
                            conn,
                            job_id=job["id"],
                            partition=partition,
                            watermark_ts=result["watermark_ts"],
                            artifact_rows=result["artifact_rows"],
                        )
                    else:
                        # 正常编排：推进该作业主水位
                        wm_repo.set_watermark(
                            conn, job["id"], result["watermark_ts"], result["artifact_rows"]
                        )
                    success_names.add(job["name"])
                except Exception as exc:  # noqa: BLE001
                    orch_repo.insert_attempt(
                        conn,
                        orchestration_id=orch_id,
                        job_id=job["id"],
                        attempt_no=1,
                        status="failed",
                        detail={"mode": mode, "partition": partition, "error": str(exc)},
                    )

        # 成功/失败/跳过一律以落库的尝试记录为准，避免报告与尝试对不上
        attempts = orch_repo.list_attempts(conn, orch_id)
        succeeded = sum(1 for a in attempts if a["status"] == "success")
        failed = sum(1 for a in attempts if a["status"] == "failed")
        skipped = sum(1 for a in attempts if a["status"] == "skipped_dep")
        report = {
            "orchestration_id": orch_id,
            "mode": mode,
            "partition": partition,
            "job_total": len(jobs),
            "succeeded": succeeded,
            "failed": failed,
            "skipped": skipped,
            "attempt_count": len(attempts),
            "watermarked_jobs": conn.execute(
                "SELECT COUNT(*) c FROM watermarks WHERE watermark_ts IS NOT NULL"
            ).fetchone()["c"],
            "partition_watermarked_jobs": (
                wm_repo.count_watermarked_partitions(conn, partition)
                if mode == "backfill"
                else 0
            ),
            "layer_count": len(layers),
        }
        status = "ok" if failed == 0 else "partial"
        orch_repo.finish_orchestration(conn, orch_id, status, report)
        conn.commit()
        return orch_repo.get_orchestration(conn, orch_id) or report
    finally:
        conn.close()
