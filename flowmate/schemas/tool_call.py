from typing import Any, Optional

from pydantic import BaseModel, Field

from flowmate.schemas.enums import ToolCallStatus


class ToolCall(BaseModel):
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    status: ToolCallStatus = ToolCallStatus.PENDING
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
