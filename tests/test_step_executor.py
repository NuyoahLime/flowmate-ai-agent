from flowmate.agent import StepExecutor, ToolExecutor
from flowmate.schemas import PlanStep, ToolCall, ToolCallStatus
from flowmate.tools import create_default_registry


def create_step_executor() -> StepExecutor:
    return StepExecutor(ToolExecutor(create_default_registry()))


def test_weather_plan_step_can_execute_successfully():
    executor = create_step_executor()
    step = PlanStep(
        id="step-weather",
        order=1,
        description="检查明早天气",
        tool_name="weather_tool",
        tool_call=ToolCall(
            tool_name="weather_tool",
            arguments={"location": "Shanghai", "date": "tomorrow"},
        ),
    )

    executed = executor.execute(step)

    assert executed.status == ToolCallStatus.SUCCESS
    assert executed.tool_call.result["condition"] == "rain"


def test_navigation_plan_step_can_execute_successfully():
    executor = create_step_executor()
    step = PlanStep(
        id="step-navigation",
        order=2,
        description="估算去公司的通勤时间",
        tool_name="navigation_tool",
        tool_call=ToolCall(
            tool_name="navigation_tool",
            arguments={
                "origin": "home",
                "destination": "company",
                "departure_time": "tomorrow 07:30",
            },
        ),
    )

    executed = executor.execute(step)

    assert executed.status == ToolCallStatus.SUCCESS
    assert executed.tool_call.result["duration_minutes"] == 42


def test_successful_step_marks_tool_call_success():
    executor = create_step_executor()
    step = PlanStep(
        id="step-weather",
        order=1,
        description="检查明早天气",
        tool_name="weather_tool",
        tool_call=ToolCall(
            tool_name="weather_tool",
            arguments={"location": "Shanghai", "date": "tomorrow"},
        ),
    )

    executed = executor.execute(step)

    assert executed.status == ToolCallStatus.SUCCESS
    assert executed.tool_call.status == ToolCallStatus.SUCCESS


def test_tool_execution_failure_marks_step_failed():
    executor = create_step_executor()
    step = PlanStep(
        id="step-weather",
        order=1,
        description="检查明早天气",
        tool_name="weather_tool",
        tool_call=ToolCall(tool_name="weather_tool", arguments={"date": "tomorrow"}),
    )

    executed = executor.execute(step)

    assert executed.status == ToolCallStatus.FAILED
    assert executed.tool_call.status == ToolCallStatus.FAILED
    assert executed.tool_call.error


def test_step_without_tool_call_is_failed():
    executor = create_step_executor()
    step = PlanStep(
        id="step-no-tool-call",
        order=1,
        description="缺少工具调用",
        tool_name="weather_tool",
        tool_call=None,
    )

    executed = executor.execute(step)

    assert executed.status == ToolCallStatus.FAILED
    assert executed.tool_call is None


def test_tool_name_mismatch_marks_step_failed():
    executor = create_step_executor()
    step = PlanStep(
        id="step-mismatch",
        order=1,
        description="工具名不一致",
        tool_name="weather_tool",
        tool_call=ToolCall(
            tool_name="navigation_tool",
            arguments={
                "origin": "home",
                "destination": "company",
                "departure_time": "tomorrow 07:30",
            },
        ),
    )

    executed = executor.execute(step)

    assert executed.status == ToolCallStatus.FAILED
    assert executed.tool_call.status == ToolCallStatus.FAILED
    assert "does not match" in executed.tool_call.error


def test_tool_name_mismatch_does_not_execute_tool():
    executor = create_step_executor()
    step = PlanStep(
        id="step-mismatch",
        order=1,
        description="工具名不一致",
        tool_name="weather_tool",
        tool_call=ToolCall(
            tool_name="navigation_tool",
            arguments={
                "origin": "home",
                "destination": "company",
                "departure_time": "tomorrow 07:30",
            },
        ),
    )

    executed = executor.execute(step)

    assert executed.tool_call.result is None
    assert executed.tool_call.error


def test_original_step_identity_fields_are_preserved():
    executor = create_step_executor()
    step = PlanStep(
        id="step-weather",
        order=3,
        description="保留原始步骤字段",
        tool_name="weather_tool",
        tool_call=ToolCall(
            tool_name="weather_tool",
            arguments={"location": "Shanghai", "date": "tomorrow"},
        ),
    )

    executed = executor.execute(step)

    assert executed.id == "step-weather"
    assert executed.order == 3
    assert executed.description == "保留原始步骤字段"
