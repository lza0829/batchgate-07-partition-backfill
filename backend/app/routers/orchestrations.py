from fastapi import APIRouter, HTTPException

from app.db import connect
from app.repositories import orchestrations as orch_repo
from app.schemas.entities import OrchestrationBody
from app.services.orchestrate_service import run_orchestration

router = APIRouter(tags=["orchestrations"])


@router.get("/orchestrations")
def list_orchestrations():
    conn = connect()
    try:
        return orch_repo.list_orchestrations(conn)
    finally:
        conn.close()


@router.get("/orchestrations/{orch_id}")
def get_orchestration(orch_id: int):
    conn = connect()
    try:
        row = orch_repo.get_orchestration(conn, orch_id)
        if not row:
            raise HTTPException(404, "not found")
        return row
    finally:
        conn.close()


@router.post("/orchestrations")
def create_orchestration(body: OrchestrationBody | None = None):
    partition = body.partition if body is not None else None
    return run_orchestration(partition=partition)
