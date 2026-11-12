from pydantic import BaseModel, Field, field_validator


class MaxAttemptsBody(BaseModel):
    max_attempts: int = Field(ge=1, le=10)


class OrchestrationBody(BaseModel):
    # 为空走正常编排（推进主水位）；带分区标识（如业务日 2026-11-08）走回补（只写分区水位）
    partition: str | None = Field(default=None)

    @field_validator("partition")
    @classmethod
    def _strip_partition(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if len(v) > 32:
            raise ValueError("partition too long (max 32 chars)")
        return v
