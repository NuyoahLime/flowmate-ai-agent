from pydantic import BaseModel

from flowmate.schemas import ConfirmationStatus, RiskLevel, Task, ToolCall


class RiskPolicyError(Exception):
    pass


class UnknownToolRiskError(RiskPolicyError):
    pass


class UnknownActionRiskError(RiskPolicyError):
    pass


class RiskAssessment(BaseModel):
    risk_level: RiskLevel
    requires_confirmation: bool
    reason: str


class RiskPolicy:
    _tool_level_risk = {
        "weather_tool": RiskLevel.LOW,
        "navigation_tool": RiskLevel.LOW,
        "calendar_tool": RiskLevel.LOW,
        "notification_tool": RiskLevel.MEDIUM,
    }
    _smart_home_action_risk = {
        ("light", "turn_on"): RiskLevel.MEDIUM,
        ("light", "turn_off"): RiskLevel.MEDIUM,
        ("air_conditioner", "turn_on"): RiskLevel.MEDIUM,
        ("air_conditioner", "turn_off"): RiskLevel.MEDIUM,
        ("air_conditioner", "set_temperature"): RiskLevel.MEDIUM,
    }
    _vehicle_action_risk = {
        "get_status": RiskLevel.LOW,
        "start_climate": RiskLevel.MEDIUM,
        "stop_climate": RiskLevel.MEDIUM,
        "lock": RiskLevel.HIGH,
        "unlock": RiskLevel.HIGH,
    }
    _priority = {
        RiskLevel.LOW: 1,
        RiskLevel.MEDIUM: 2,
        RiskLevel.HIGH: 3,
    }

    def assess(self, tool_names: list[str]) -> RiskAssessment:
        risks = [self._assess_tool_name(tool_name) for tool_name in tool_names]
        return self._highest_risk_assessment(risks, tool_names)

    def assess_tool_call(self, tool_call: ToolCall) -> RiskAssessment:
        if tool_call.tool_name == "smart_home_tool":
            device_type = tool_call.arguments.get("device_type")
            action = tool_call.arguments.get("action")
            key = (device_type, action)
            try:
                risk = self._smart_home_action_risk[key]
            except KeyError as exc:
                raise UnknownActionRiskError(
                    "No deterministic smart-home risk policy for "
                    f"device_type={device_type!r}, action={action!r}."
                ) from exc
        elif tool_call.tool_name == "vehicle_tool":
            action = tool_call.arguments.get("action")
            try:
                risk = self._vehicle_action_risk[action]
            except KeyError as exc:
                raise UnknownActionRiskError(
                    f"No deterministic vehicle risk policy for action={action!r}."
                ) from exc
        else:
            risk = self._assess_tool_name(tool_call.tool_name)

        return self._highest_risk_assessment([risk], [tool_call.tool_name])

    def assess_tool_calls(self, tool_calls: list[ToolCall]) -> RiskAssessment:
        assessments = [self.assess_tool_call(tool_call) for tool_call in tool_calls]
        risks = [assessment.risk_level for assessment in assessments]
        tool_names = [tool_call.tool_name for tool_call in tool_calls]
        return self._highest_risk_assessment(risks, tool_names)

    def assess_task(self, task: Task) -> RiskAssessment:
        tool_calls: list[ToolCall] = []
        name_only_tools: list[str] = []
        for step in task.steps:
            if step.tool_call is None:
                name_only_tools.append(step.tool_name)
            else:
                tool_calls.append(step.tool_call)

        assessments = [self.assess_tool_call(tool_call) for tool_call in tool_calls]
        assessments.extend(
            self._highest_risk_assessment(
                [self._assess_tool_name(tool_name)],
                [tool_name],
            )
            for tool_name in name_only_tools
        )
        return self._highest_risk_assessment(
            [assessment.risk_level for assessment in assessments],
            [step.tool_name for step in task.steps],
        )

    def apply_to_task(self, task: Task) -> Task:
        assessment = self.assess_task(task)
        task.risk_level = assessment.risk_level
        task.requires_confirmation = assessment.requires_confirmation
        task.confirmation_status = (
            ConfirmationStatus.PENDING
            if assessment.requires_confirmation
            else ConfirmationStatus.NOT_REQUIRED
        )
        return task

    def _assess_tool_name(self, tool_name: str) -> RiskLevel:
        if tool_name in {"smart_home_tool", "vehicle_tool"}:
            raise UnknownActionRiskError(
                f"{tool_name} risk requires validated action arguments."
            )
        try:
            return self._tool_level_risk[tool_name]
        except KeyError as exc:
            raise UnknownToolRiskError(
                f"No deterministic risk policy for tool: {tool_name}"
            ) from exc

    def _highest_risk_assessment(
        self,
        risks: list[RiskLevel],
        tool_names: list[str],
    ) -> RiskAssessment:
        if not risks:
            return RiskAssessment(
                risk_level=RiskLevel.LOW,
                requires_confirmation=False,
                reason="No tools planned; defaulting to LOW risk.",
            )

        highest_risk = max(
            risks,
            key=lambda risk_level: self._priority[risk_level],
        )
        return RiskAssessment(
            risk_level=highest_risk,
            requires_confirmation=highest_risk != RiskLevel.LOW,
            reason=(
                "Highest deterministic risk policy applied to planned tools: "
                f"{', '.join(tool_names)}."
            ),
        )
