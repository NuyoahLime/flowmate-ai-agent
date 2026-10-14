from flowmate.agent.tool_executor import ToolExecutor
from flowmate.schemas import PlanStep, ToolCallStatus


class StepExecutor:
    def __init__(self, tool_executor: ToolExecutor) -> None:
        self.tool_executor = tool_executor

    def execute(self, step: PlanStep) -> PlanStep:
        if step.tool_call is None:
            step.status = ToolCallStatus.FAILED
            return step

        if step.tool_name != step.tool_call.tool_name:
            step.status = ToolCallStatus.FAILED
            step.tool_call.status = ToolCallStatus.FAILED
            step.tool_call.result = None
            step.tool_call.error = (
                "PlanStep tool_name does not match ToolCall tool_name: "
                f"{step.tool_name} != {step.tool_call.tool_name}"
            )
            return step

        step.status = ToolCallStatus.RUNNING
        step.tool_call = self.tool_executor.execute(step.tool_call)

        if step.tool_call.status == ToolCallStatus.SUCCESS:
            step.status = ToolCallStatus.SUCCESS
        else:
            step.status = ToolCallStatus.FAILED

        return step
