from pydantic import ValidationError

from flowmate.schemas import ToolCall, ToolCallStatus
from flowmate.tools import ToolNotFoundError, ToolRegistry


class ToolExecutor:
    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def execute(self, tool_call: ToolCall) -> ToolCall:
        tool_call.status = ToolCallStatus.RUNNING
        tool_call.result = None
        tool_call.error = None

        try:
            tool = self.registry.get(tool_call.tool_name)
            result = tool.run(tool_call.arguments)
            tool_call.status = ToolCallStatus.SUCCESS
            tool_call.result = result.model_dump()
            tool_call.error = None
        except ToolNotFoundError as exc:
            self._mark_failed(tool_call, exc)
        except ValidationError as exc:
            self._mark_failed(tool_call, exc)
        except Exception as exc:
            self._mark_failed(tool_call, exc)

        return tool_call

    def _mark_failed(self, tool_call: ToolCall, exc: Exception) -> None:
        tool_call.status = ToolCallStatus.FAILED
        tool_call.result = None
        tool_call.error = f"{exc.__class__.__name__}: {exc}"
