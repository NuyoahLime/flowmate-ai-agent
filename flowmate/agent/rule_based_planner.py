from uuid import uuid4

from flowmate.agent.planner import UnsupportedPlanningScenarioError
from flowmate.schemas import PlanStep, RiskLevel, Task, TaskStatus, ToolCall


class RuleBasedPlanner:
    _morning_commute_patterns = (
        ("公司", "开会"),
        ("公司", "出门"),
        ("上班", "通勤"),
        ("上班", "出门"),
        ("通勤",),
    )

    def plan(self, user_input: str) -> Task:
        if not self._is_morning_commute(user_input):
            raise UnsupportedPlanningScenarioError(
                "Unsupported planning scenario. Only morning_commute is supported."
            )

        return Task(
            id=f"task-{uuid4()}",
            user_input=user_input,
            goal="安排明早通勤，确保按时到达公司",
            status=TaskStatus.PLANNED,
            risk_level=RiskLevel.LOW,
            requires_confirmation=False,
            steps=[
                PlanStep(
                    id=f"step-{uuid4()}",
                    order=1,
                    description="检查明早天气",
                    tool_name="weather_tool",
                    tool_call=ToolCall(
                        tool_name="weather_tool",
                        arguments={
                            "location": "current_city",
                            "date": "tomorrow",
                        },
                    ),
                ),
                PlanStep(
                    id=f"step-{uuid4()}",
                    order=2,
                    description="计算到公司的通勤时间",
                    tool_name="navigation_tool",
                    tool_call=ToolCall(
                        tool_name="navigation_tool",
                        arguments={
                            "origin": "home",
                            "destination": "company",
                            "departure_time": "tomorrow morning",
                        },
                    ),
                ),
            ],
        )

    def _is_morning_commute(self, user_input: str) -> bool:
        normalized_input = user_input.strip()
        return any(
            all(keyword in normalized_input for keyword in pattern)
            for pattern in self._morning_commute_patterns
        )
