from typing import Optional

from pydantic import BaseModel

from flowmate.schemas.enums import ToolCallStatus
from flowmate.schemas.tool_call import ToolCall


class PlanStep(BaseModel):
    id: str
    order: int
    description: str
    tool_name: str
    tool_call: Optional[ToolCall] = None
    status: ToolCallStatus = ToolCallStatus.PENDING
