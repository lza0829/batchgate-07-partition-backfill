"""分区回补与主水位分轨的端到端测试。"""

import json
from pathlib import Path

import pytest

from app import db
from app.engines.job_runner import run_fixture_job
from app.repositories import watermarks as wm_repo
from app.seed import init_db
from app.services.orchestrate_service import run_orchestration


@pytest.fixture()
def temp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)
    init_db()
    return db_path


def test_run_fixture_partition_branch(tmp_path: Path):
    p = tmp_path / "x.json"
    p.write_text(
        json.dumps(
            {
                "watermark_ts": "2026-01-03T00:00:00Z",
                "rows": [{"id": 1}],
                "partition_data": {
                    "2026-01-01": {
                        "watermark_ts": "2026-01-01T00:00:00Z",
                        "rows": [{"id": 9}, {"id": 10}],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    normal = run_fixture_job(p)
    assert normal["mode"] == "normal" and normal["partition"] is None
    assert normal["artifact_rows"] == 1

    backfill = run_fixture_job(p, "2026-01-01")
    assert backfill["mode"] == "backfill"
    assert backfill["partition"] == "2026-01-01"
    assert backfill["artifact_rows"] == 2

    with pytest.raises(ValueError):
        run_fixture_job(p, "missing-partition")


def test_normal_run_updates_main_watermark_only(temp_db: Path):
    result = run_orchestration()
    assert result["mode"] == "normal"
    assert result["partition"] is None
    report = result["report"]
    assert report["mode"] == "normal" and report["partition"] is None

    conn = db.connect()
    try:
        mains = wm_repo.list_watermarks(conn)
        assert len(mains) == 3
        assert all(w["watermark_ts"] is not None for w in mains)
        # 正常编排不产生分区水位
        assert wm_repo.list_partition_watermarks(conn) == []
    finally:
        conn.close()

    # 报告计数与尝试记录一致
    assert report["succeeded"] == 3
    assert report["failed"] == 0
    assert report["skipped"] == 0
    assert report["attempt_count"] == (
        report["succeeded"] + report["failed"] + report["skipped"]
    )


def test_backfill_writes_partition_and_keeps_main_untouched(temp_db: Path):
    run_orchestration()  # 先跑一次正常编排，建立主水位
    conn = db.connect()
    try:
        before = {w["job_id"]: w["watermark_ts"] for w in wm_repo.list_watermarks(conn)}
    finally:
        conn.close()

    result = run_orchestration(partition="2026-11-08")
    assert result["status"] == "ok"
    report = result["report"]
    assert report["mode"] == "backfill"
    assert report["partition"] == "2026-11-08"
    assert report["succeeded"] == 3
    assert report["partition_watermarked_jobs"] == 3

    conn = db.connect()
    try:
        after = {w["job_id"]: w["watermark_ts"] for w in wm_repo.list_watermarks(conn)}
        # 回补不得抬主水位
        assert after == before

        parts = wm_repo.list_partition_watermarks(conn, "2026-11-08")
        assert len(parts) == 3
        ingest = next(p for p in parts if p["job_name"] == "ingest_orders")
        assert ingest["watermark_ts"].startswith("2026-11-08")
        assert ingest["watermark_ts"] != before[ingest["job_id"]]
    finally:
        conn.close()


def test_backfill_unknown_partition_fails_without_touching_watermarks(temp_db: Path):
    result = run_orchestration(partition="2020-01-01")
    assert result["status"] == "partial"
    report = result["report"]
    assert report["mode"] == "backfill"
    assert report["partition"] == "2020-01-01"
    # 两个无依赖的根作业取分区数据失败；下游因上游未成功被依赖闸跳过
    assert report["failed"] == 2
    assert report["skipped"] == 1
    assert report["succeeded"] == 0
    assert report["attempt_count"] == report["failed"] + report["skipped"]

    conn = db.connect()
    try:
        # 失败不产生任何水位
        assert wm_repo.list_partition_watermarks(conn) == []
        assert all(w["watermark_ts"] is None for w in wm_repo.list_watermarks(conn))
    finally:
        conn.close()


def test_multiple_partitions_persist_and_stay_separate(temp_db: Path):
    run_orchestration(partition="2026-11-08")
    run_orchestration(partition="2026-11-09")

    # 重新打开连接，确认刷新/重连后分区结果仍在（SQLite 持久化）
    conn = db.connect()
    try:
        rows = wm_repo.list_partition_watermarks(conn)
        assert {(r["job_name"], r["partition"]) for r in rows} == {
            (job, day)
            for day in ("2026-11-08", "2026-11-09")
            for job in ("ingest_orders", "dim_customer", "fact_order_daily")
        }
        # 只跑过回补：主水位始终为空
        assert all(w["watermark_ts"] is None for w in wm_repo.list_watermarks(conn))

        day8 = wm_repo.list_partition_watermarks(conn, "2026-11-08")
        day9 = wm_repo.list_partition_watermarks(conn, "2026-11-09")
        assert {r["watermark_ts"] for r in day8} != {r["watermark_ts"] for r in day9}
    finally:
        conn.close()
