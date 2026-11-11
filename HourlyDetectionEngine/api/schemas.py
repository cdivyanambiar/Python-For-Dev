"""Request schemas (Pydantic v2): validate at the system boundary, trust inside."""
from __future__ import annotations

from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

SOURCE_PATTERN = r"^[a-z][a-z0-9_]{0,31}$"


class EventIn(BaseModel):
    event_id: str = Field(min_length=1, max_length=128)
    source: str = Field(pattern=SOURCE_PATTERN)
    event_time: AwareDatetime
    attributes: dict[str, Any] = Field(default_factory=dict)


class EventBatch(BaseModel):
    events: list[EventIn] = Field(min_length=1, max_length=10_000)


class RunRequest(BaseModel):
    hour: AwareDatetime | None = Field(None, description="Any time inside the hour to run; default = previous hour")
    sources: list[str] | None = None


class RuleIn(BaseModel):
    """Common fields are checked here; type-specific fields are checked by the rule factory."""

    model_config = ConfigDict(extra="allow")

    rule_id: str = Field(pattern=r"^[A-Za-z0-9_\-]{1,64}$")
    source: str = Field(pattern=SOURCE_PATTERN)
    type: str = "pattern"
    severity: str = "medium"
    description: str = Field("", max_length=500)
    enabled: bool = True
