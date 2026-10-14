from typing import Any, Mapping
from uuid import uuid4

from pydantic import ValidationError

from flowmate.agent.explicit_constraint_validator import ExplicitConstraintValidator
from flowmate.agent.llm_client import LLMClient
from flowmate.agent.planner import (
    PlannerOutputValidationError,
    UnsupportedPlanningScenarioError,
)
from flowmate.agent.risk_policy import RiskPolicy
from flowmate.agent.tool_argument_validator import (
    ToolArgumentValidationError,
    ToolArgumentValidator,
    build_planner_tool_spec,
)
from flowmate.agent.temporal_conventions import (
    build_calendar_temporal_conventions_prompt,
)
from flowmate.schemas import LLMPlanResponse, PlannedTask, PlanStep, Task, TaskStatus, ToolCall
from flowmate.tools import ToolRegistry, create_default_registry

LLM_PLANNER_PROMPT_TEMPLATE = """
You are FlowMate's task planning module.

Plan only. Do not execute tools.

The only available tools are:

{tool_spec}

{calendar_temporal_conventions}

For Morning Commute tasks, produce reasonable steps using only the available tools.
When the user asks FlowMate to arrange morning departure for work or a company
meeting, weather and navigation are directly implied. When the user asks only
for route, distance, or travel duration, use navigation only. When the user asks
only for weather, use weather only.

Preserve every explicit user-provided constraint in the relevant tool arguments:
- dates and clock times
- origins and destinations
- device or vehicle targets
- requested actions
Explicit values take precedence over canonical mappings and defaults. Never replace an
explicit origin such as 心理所 or 学校 with home. Never degrade a specific clock time
such as 09:00 or 下午6点 to morning, tomorrow morning, or another broad daypart.
When navigation is for tomorrow at a specific time, departure_time must preserve both
the date and clock time, for example tomorrow 09:00 or tomorrow 18:00.
If a route request provides an origin but no destination, return unsupported as
insufficiently specified. Do not invent a destination or query Calendar for one.

This baseline does not require address extraction. Use these canonical mappings
only when they are directly implied by the user's request:
- here, local area, or the user's current city => current_city
- home or starting from home => home
- company, office, workplace, or unit => company
- work commute, driving to work, or going to the company by car without an
  explicit origin => home
- navigation_tool.departure_time: use tomorrow morning for tomorrow morning,
  morning departure, morning commute, or an unspecified work commute; do not use
  now unless the user asks for now
- weather_tool.date: use tomorrow for tomorrow, tomorrow morning, or tomorrow's weather
Do not reject a supported request merely because exact addresses are missing
when a canonical mapping above applies.

Capability decision rule:
1. Identify the user's actual requested outcome.
2. Decide whether that outcome is information/planning or real-world physical control.
3. Check whether an available tool can provide that outcome.
4. Mark unsupported only if the requested outcome itself exceeds available tool capabilities.

Only consider a task supported when the available tools can actually perform the user's
requested goal. A tool being related to the topic is not sufficient. For example,
navigation_tool can calculate a route, but it cannot drive or move a vehicle.
Requests to move a vehicle, control an unsupported vehicle or home device, or
write a calendar must be unsupported except for the explicitly supported
smart-home and vehicle actions below.

notification_tool supports immediate mock mobile notifications only when the user
explicitly asks FlowMate to send a notification now. It requires:
- title
- message
- channel=mobile
Do not add notification_tool unless the user explicitly requests a notification
or immediate user-facing message delivery.
Scheduled, delayed, conditional, email, SMS, WeChat, or guaranteed real push
notifications are unsupported. Do not convert future reminders or conditional
alerts into immediate notifications.

smart_home_tool supports explicit, immediate mock control only for:
- light: turn_on, turn_off
- air_conditioner: turn_on, turn_off, set_temperature
It requires device_id, device_type, and action. set_temperature also requires
value between 16 and 30 degrees Celsius. Use these mock logical device mappings
only when the room and device are explicitly identified:
- living room light => living-room-light
- bedroom light => bedroom-light
- study room light => study-room-light
- bedroom air conditioner => bedroom-ac
- living room air conditioner => living-room-ac
Do not guess a default room or device when the user says only light or air
conditioner without a location. Return unsupported as insufficiently specified.
Scheduled, delayed, conditional, scene-based, or state-verification smart-home
requests are unsupported. Unsupported devices include curtains, televisions,
door locks, and cameras. Do not use smart_home_tool unless the user explicitly
requests immediate control of a supported device. Smart-home control is mock;
do not claim or verify that a real physical device changed state.

vehicle_tool supports explicit, immediate mock vehicle actions only:
- get_status
- lock
- unlock
- start_climate
- stop_climate
It requires vehicle_id and action. start_climate may include temperature from
16 to 30 degrees Celsius. When the user explicitly refers to their car or
vehicle without another identifier, use the mock logical vehicle_id=my-car.
get_status returns only the mock locked state and climate on/off state. It cannot
report fuel, battery or charge level, location, speed, mileage, tire pressure, or
other vehicle telemetry; requests for those unavailable fields are unsupported.
Do not use vehicle_tool unless a supported vehicle status or control action is
explicitly requested. Vehicle movement, remote driving, autonomous driving,
summon, engine control, trunk/window control, horn, lights, and charging are
unsupported. Scheduled, delayed, conditional, and proactive vehicle control are
unsupported. Vehicle control is mock; do not claim or verify that a real vehicle
changed state.

Keep navigation and vehicle control separate. Route planning uses
navigation_tool, including when the user says they will drive themselves. A
request for FlowMate to drive, move, summon, or relocate a vehicle is unsupported
and must not be converted into route planning or a vehicle control action.

Calendar read requests are supported when the user asks to query schedules,
meetings, calendar events, or events within a time window. Calendar read is
low risk and should use requires_confirmation=false.

When the user explicitly provides a daypart or time window, preserve that
temporal constraint in calendar_tool arguments. Optional schema fields must
still be populated when they are necessary to preserve an explicit user
constraint.

Calendar write requests are unsupported. Requests to create, update, delete,
accept, reject, cancel, reschedule, or modify calendar events must be unsupported.
Calendar topic related does not imply calendar write capability.

Plans whose later tool arguments depend on runtime results from an earlier tool
are unsupported in this version. For example, do not first query a meeting and
then guess navigation_tool arguments from the unexecuted calendar result. Return
unsupported instead of guessing meeting time, location, route, or departure time.

When the user says they will perform the physical action themselves and asks the
assistant only for information or planning, evaluate the informational request
rather than treating the task as physical control. Do not reject a supported
information request merely because the surrounding context mentions driving, a
vehicle, or another unsupported physical action domain.

If the user asks the assistant to drive, move, summon, relocate, start an engine,
or perform another unsupported vehicle action, that is unsupported physical
control. Do not map it to navigation_tool or the nearest vehicle action.

Only include a tool when its output is necessary to satisfy an explicit
or directly implied part of the user's goal.
Do not add optional contextual tools merely because they might be useful.
Use the smallest sufficient set of tools.

When selecting a tool, provide every required argument defined by that tool's schema.
Do not omit a required field when the user's request provides or directly implies
the necessary information. Use only argument keys defined by the selected tool's schema.
Extra argument keys are invalid. Do not invent values for information that is
unavailable and not covered by the canonical mappings above.

If the user's goal cannot be supported by these tools, return unsupported instead of guessing.
Output must be one valid JSON object matching the LLMPlanResponse envelope.
For supported tasks, put the PlannedTask object in "plan".
For unsupported tasks, set "unsupported" to true, provide a "reason", and set "plan" to null.

Supported JSON example:
{
  "unsupported": false,
  "reason": null,
  "plan": {
    "goal": "安排明早通勤",
    "risk_level": "LOW",
    "requires_confirmation": false,
    "steps": [
      {
        "order": 1,
        "description": "检查明早天气",
        "tool_name": "weather_tool",
        "arguments": {
          "location": "current_city",
          "date": "tomorrow"
        }
      },
      {
        "order": 2,
        "description": "计算到公司的通勤时间",
        "tool_name": "navigation_tool",
        "arguments": {
          "origin": "home",
          "destination": "company",
          "departure_time": "tomorrow 08:30"
        }
      }
    ]
  }
}

Use these exact field names. Do not add a "task" field or use "tool" instead of "tool_name".
"""


def build_llm_planner_prompt(
    registry: ToolRegistry | None = None,
    allowed_tools: set[str] | None = None,
) -> str:
    registry = registry or create_default_registry()
    allowed_tools = allowed_tools or {
        "weather_tool",
        "navigation_tool",
        "calendar_tool",
        "notification_tool",
        "smart_home_tool",
        "vehicle_tool",
    }
    return LLM_PLANNER_PROMPT_TEMPLATE.replace(
        "{tool_spec}",
        build_planner_tool_spec(registry, allowed_tools),
    ).replace(
        "{calendar_temporal_conventions}",
        build_calendar_temporal_conventions_prompt(),
    )


LLM_PLANNER_PROMPT = build_llm_planner_prompt()


class LLMPlanner:
    def __init__(
        self,
        client: LLMClient,
        allowed_tools: set[str] | None = None,
        tool_registry: ToolRegistry | None = None,
        tool_argument_validator: ToolArgumentValidator | None = None,
        explicit_constraint_validator: ExplicitConstraintValidator | None = None,
        risk_policy: RiskPolicy | None = None,
    ) -> None:
        self.client = client
        self.tool_registry = tool_registry or create_default_registry()
        self.allowed_tools = allowed_tools or {
            "weather_tool",
            "navigation_tool",
            "calendar_tool",
            "notification_tool",
            "smart_home_tool",
            "vehicle_tool",
        }
        self.tool_argument_validator = tool_argument_validator or ToolArgumentValidator(
            self.tool_registry
        )
        self.explicit_constraint_validator = (
            explicit_constraint_validator or ExplicitConstraintValidator()
        )
        self.risk_policy = risk_policy or RiskPolicy()
        self.system_prompt = build_llm_planner_prompt(
            self.tool_registry,
            self.allowed_tools,
        )

    def plan(self, user_input: str) -> Task:
        raw_output = self.client.generate_plan(
            user_input=user_input,
            system_prompt=self.system_prompt,
        )

        if not isinstance(raw_output, Mapping):
            raise PlannerOutputValidationError("LLM planner output must be a mapping.")

        provider_response = self._parse_provider_response(raw_output)
        if provider_response.unsupported:
            raise UnsupportedPlanningScenarioError(str(provider_response.reason))

        planned_task = provider_response.plan
        if planned_task is None:
            raise PlannerOutputValidationError("Supported LLM planner output has no plan.")

        self._validate_tool_whitelist(planned_task)
        self._validate_tool_arguments(planned_task)
        self.explicit_constraint_validator.validate(user_input, planned_task)

        task = Task(
            id=f"task-{uuid4()}",
            user_input=user_input,
            goal=planned_task.goal,
            status=TaskStatus.PLANNED,
            risk_level=planned_task.risk_level,
            requires_confirmation=planned_task.requires_confirmation,
            steps=[
                PlanStep(
                    id=f"step-{uuid4()}",
                    order=step.order,
                    description=step.description,
                    tool_name=step.tool_name,
                    tool_call=ToolCall(
                        tool_name=step.tool_name,
                        arguments=step.arguments,
                    ),
                )
                for step in sorted(planned_task.steps, key=lambda item: item.order)
            ],
        )
        return self.risk_policy.apply_to_task(task)

    def _parse_provider_response(self, raw_output: Mapping[str, Any]) -> LLMPlanResponse:
        try:
            return LLMPlanResponse.model_validate(raw_output)
        except ValidationError as exc:
            raise PlannerOutputValidationError(f"Invalid LLM planner output: {exc}") from exc

    def _validate_tool_whitelist(self, planned_task: PlannedTask) -> None:
        invalid_tools = [
            step.tool_name
            for step in planned_task.steps
            if step.tool_name not in self.allowed_tools
        ]

        if invalid_tools:
            raise PlannerOutputValidationError(
                f"LLM planner output contains unsupported tools: {', '.join(invalid_tools)}"
            )

    def _validate_tool_arguments(self, planned_task: PlannedTask) -> None:
        predicted_tools = [step.tool_name for step in planned_task.steps]
        predicted_arguments = {
            step.tool_name: dict(step.arguments)
            for step in planned_task.steps
        }

        for step in planned_task.steps:
            try:
                self.tool_argument_validator.validate(step.tool_name, step.arguments)
            except ToolArgumentValidationError as exc:
                raise ToolArgumentValidationError(
                    str(exc),
                    tool_name=step.tool_name,
                    arguments=step.arguments,
                    predicted_tools=predicted_tools,
                    predicted_arguments=predicted_arguments,
                ) from exc
