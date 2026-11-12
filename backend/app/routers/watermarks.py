from fastapi import APIRouter

from app.db import connect
from app.repositories import watermarks as wm_repo

router = APIRouter(tags=["watermarks"])


@router.get("/watermarks")
def list_watermarks():
    """主水位：每个作业一行，只由正常编排推进。"""
    conn = connect()
    try:
        return wm_repo.list_watermarks(conn)
    finally:
        conn.close()


@router.get("/partition-watermarks")
def list_partition_watermarks(partition: str | None = None):
    """分区水位：(作业, 分区) 一行，只由回补编排写入，与主水位分开查。"""
    conn = connect()
    try:
        return wm_repo.list_partition_watermarks(conn, partition)
    finally:
        conn.close()
