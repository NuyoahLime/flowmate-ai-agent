from uuid import uuid4

from flowmate.agent.notification_formatter import (
    NotificationFormatter,
    NotificationGroundingError,
)
from flowmate.agent.risk_policy import RiskPolicy, UnknownToolRiskError
from flowmate.agent.step_executor import StepExecutor
from flowmate.agent.task_confirmation import TaskConfirmationService, TaskConfirmationError
from flowmate.agent.task_executor import TaskExecutor, TaskExecutionError
from flowmate.agent.tool_executor import ToolExecutor
from flowmate.schemas import (
    DynamicPlanningFailureType,
    DynamicPlanningPhase,
    DynamicPlanningState,
    DynamicTaskResult,
    PlanStep,
    RiskLevel,
    Task,
    TaskStatus,
    ToolCall,
    ToolCallStatus,
    ToolObservation,
)


class DynamicPlanningError(Exception):
    pass


class ObservationDrivenContinuationPlanner:
    def build_continuation_steps(
        self,
        *,
        user_input: str,
        selected_event: dict,
        start_order: int,
    ) -> list[PlanStep]:
        location = selected_event.get("location")
        if not location:
            raise DynamicPlanningError(
                "Calendar event has no location required for navigation planning."
            )

        steps: list[PlanStep] = []
        if self._requires_weather(user_input):
            steps.append(
                PlanStep(
                    id=f"step-{uuid4()}",
                    order=start_order,
                    description="Check tomorrow morning weather.",
                    tool_name="weather_tool",
                    tool_call=ToolCall(
                        tool_name="weather_tool",
                        arguments={
                            "location": "current_city",
                            "date": "tomorrow",
                        },
                    ),
                )
            )
            start_order += 1

        steps.append(
            PlanStep(
                id=f"step-{uuid4()}",
                order=start_order,
                description="Plan the commute route to the selected calendar event.",
                tool_name="navigation_tool",
                tool_call=ToolCall(
                    tool_name="navigation_tool",
                    arguments={
                        "origin": "home",
                        "destination": location,
                        "departure_time": "tomorrow morning",
                    },
                ),
            )
        )
        return steps

    def _requires_weather(self, user_input: str) -> bool:
        lowered = user_input.lower()
        weather_markers = ("weather", "rain", "temperature", "天气", "下雨", "气温")
        return any(marker in lowered for marker in weather_markers)


class DynamicTaskOrchestrator:
    def __init__(
        self,
        tool_executor: ToolExecutor,
        continuation_planner: ObservationDrivenContinuationPlanner | None = None,
        notification_formatter: NotificationFormatter | None = None,
        risk_policy: RiskPolicy | None = None,
        confirmation_service: TaskConfirmationService | None = None,
        task_executor: TaskExecutor | None = None,
        max_iterations: int = 2,
        execute_continuation_tools: bool = True,
    ) -> None:
        if max_iterations < 1:
            raise ValueError("max_iterations must be >= 1.")
        self.tool_executor = tool_executor
        self.continuation_planner = (
            continuation_planner or ObservationDrivenContinuationPlanner()
        )
        self.notification_formatter = notification_formatter or NotificationFormatter()
        self.risk_policy = risk_policy or RiskPolicy()
        self.confirmation_service = confirmation_service or TaskConfirmationService()
        self.task_executor = task_executor or TaskExecutor(StepExecutor(tool_executor))
        self.max_iterations = max_iterations
        self.execute_continuation_tools = execute_continuation_tools

    def execute(self, user_input: str) -> DynamicPlanningState:
        state = DynamicPlanningState(
            user_input=user_input,
            max_iterations=self.max_iterations,
        )

        if not self.is_dynamic_request(user_input):
            return self._fail(
                state,
                DynamicPlanningFailureType.UNSUPPORTED_DYNAMIC_GOAL,
                "This request does not require runtime observation-driven planning.",
            )

        if self._has_conditional_notification_request(user_input):
            return self._fail(
                state,
                DynamicPlanningFailureType.UNSUPPORTED_CONDITIONAL_NOTIFICATION,
                "Conditional notification requires triggers and is unsupported.",
            )

        if self._has_scheduled_notification_request(user_input):
            return self._fail(
                state,
                DynamicPlanningFailureType.UNSUPPORTED_SCHEDULED_NOTIFICATION,
                "Scheduled notification requires a scheduler and is unsupported.",
            )

        if self._max_iterations_reached(state):
            return self._fail(
                state,
                DynamicPlanningFailureType.MAX_ITERATIONS_EXCEEDED,
                "Dynamic planning exceeded max_iterations before initial planning.",
            )

        state.task = self._build_initial_calendar_task(user_input)
        state.iteration_count += 1
        state.phase = DynamicPlanningPhase.WAITING_OBSERVATION

        calendar_step = state.task.steps[0]
        executed_call = self.tool_executor.execute(calendar_step.tool_call)
        calendar_step.tool_call = executed_call
        calendar_step.status = executed_call.status

        observation = ToolObservation(
            tool_name=executed_call.tool_name,
            step_id=calendar_step.id,
            result=executed_call.result or {},
            error=executed_call.error,
        )
        state.observations.append(observation)

        if executed_call.status == ToolCallStatus.FAILED:
            return self._fail(
                state,
                DynamicPlanningFailureType.TOOL_EXECUTION_ERROR,
                executed_call.error or "Calendar tool execution failed.",
            )

        selected_event = self._select_earliest_event(observation)
        if selected_event is None:
            return self._fail(
                state,
                DynamicPlanningFailureType.NO_CALENDAR_EVENT,
                "No morning calendar event found to anchor departure planning.",
            )

        state.selected_event = selected_event
        if not selected_event.get("location"):
            return self._fail(
                state,
                DynamicPlanningFailureType.MISSING_EVENT_LOCATION,
                "Calendar event has no location required for navigation planning.",
            )

        if self._max_iterations_reached(state):
            return self._fail(
                state,
                DynamicPlanningFailureType.MAX_ITERATIONS_EXCEEDED,
                "Dynamic planning exceeded max_iterations before continuation planning.",
            )

        state.phase = DynamicPlanningPhase.CONTINUATION_PLANNING
        try:
            continuation_steps = self.continuation_planner.build_continuation_steps(
                user_input=user_input,
                selected_event=selected_event,
                start_order=2,
            )
        except DynamicPlanningError as exc:
            return self._fail(
                state,
                DynamicPlanningFailureType.CONTINUATION_PLANNING_ERROR,
                str(exc),
            )

        state.task.steps.extend(continuation_steps)
        state.task.status = TaskStatus.PLANNED
        state.iteration_count += 1

        grounding_error = self._validate_navigation_grounding(state, continuation_steps)
        if grounding_error is not None:
            return self._fail(
                state,
                DynamicPlanningFailureType.OBSERVATION_GROUNDING_ERROR,
                grounding_error,
            )

        if not self.execute_continuation_tools:
            state.phase = DynamicPlanningPhase.COMPLETED
            state.final_result = self._build_final_result(state)
            return state

        state.phase = DynamicPlanningPhase.CONTINUATION_EXECUTING
        return self.execute_continuation_steps(state)

    def execute_continuation_steps(
        self,
        state: DynamicPlanningState,
    ) -> DynamicPlanningState:
        if state.task is None:
            return self._fail(
                state,
                DynamicPlanningFailureType.CONTINUATION_EXECUTION_ERROR,
                "Cannot execute continuation steps without a Task.",
            )

        continuation_steps = sorted(state.task.steps[1:], key=lambda step: step.order)
        for step in continuation_steps:
            if step.tool_call is None:
                step.status = ToolCallStatus.FAILED
                return self._fail(
                    state,
                    DynamicPlanningFailureType.CONTINUATION_EXECUTION_ERROR,
                    f"Continuation step has no ToolCall: {step.id}",
                )

            executed_call = self.tool_executor.execute(step.tool_call)
            step.tool_call = executed_call
            step.status = executed_call.status
            observation = ToolObservation(
                tool_name=executed_call.tool_name,
                step_id=step.id,
                result=executed_call.result or {},
                error=executed_call.error,
            )
            state.continuation_observations.append(observation)

            if executed_call.status == ToolCallStatus.FAILED:
                return self._fail(
                    state,
                    DynamicPlanningFailureType.CONTINUATION_EXECUTION_ERROR,
                    (
                        f"{executed_call.tool_name} failed: "
                        f"{executed_call.error or 'unknown tool execution error'}"
                    ),
                )

        state.task.status = TaskStatus.COMPLETED
        state.phase = DynamicPlanningPhase.COMPLETED
        state.final_result = self._build_final_result(state)
        if self._notification_requested(state.user_input):
            return self._prepare_side_effect(state)
        return state

    def confirm_side_effect(self, state: DynamicPlanningState) -> DynamicPlanningState:
        if state.notification_task is None:
            return self._fail(
                state,
                DynamicPlanningFailureType.SIDE_EFFECT_PROPOSAL_ERROR,
                "No notification task is waiting for confirmation.",
            )

        try:
            self.confirmation_service.confirm(state.notification_task)
            state.phase = DynamicPlanningPhase.SIDE_EFFECT_EXECUTING
            executed_task = self.task_executor.execute(state.notification_task)
        except (TaskConfirmationError, TaskExecutionError) as exc:
            return self._fail(
                state,
                DynamicPlanningFailureType.SIDE_EFFECT_EXECUTION_ERROR,
                str(exc),
            )

        state.notification_task = executed_task
        if executed_task.status != TaskStatus.COMPLETED:
            return self._fail(
                state,
                DynamicPlanningFailureType.SIDE_EFFECT_EXECUTION_ERROR,
                "Notification side-effect Task failed.",
            )

        state.notification_result = executed_task.steps[0].tool_call.result
        state.side_effect_status = "executed"
        state.phase = DynamicPlanningPhase.COMPLETED
        state.final_result = self._build_final_result(state)
        return state

    def reject_side_effect(self, state: DynamicPlanningState) -> DynamicPlanningState:
        if state.notification_task is None:
            return self._fail(
                state,
                DynamicPlanningFailureType.SIDE_EFFECT_PROPOSAL_ERROR,
                "No notification task is waiting for rejection.",
            )

        try:
            self.confirmation_service.reject(state.notification_task)
        except TaskConfirmationError as exc:
            return self._fail(
                state,
                DynamicPlanningFailureType.SIDE_EFFECT_PROPOSAL_ERROR,
                str(exc),
            )

        state.side_effect_status = "rejected"
        state.phase = DynamicPlanningPhase.CANCELLED
        state.final_result = self._build_final_result(state)
        return state

    def is_dynamic_request(self, user_input: str) -> bool:
        text = user_input.lower()
        has_morning = any(
            marker in text
            for marker in (
                "明早",
                "明天早上",
                "明天上午",
                "tomorrow morning",
                "morning",
            )
        )
        has_departure_or_route = any(
            marker in text
            for marker in (
                "出门",
                "通勤",
                "路线",
                "怎么过去",
                "departure",
                "commute",
                "route",
                "how to get there",
            )
        )
        has_runtime_anchor = any(
            marker in text
            for marker in (
                "会议",
                "日程",
                "安排",
                "第一场",
                "calendar",
                "meeting",
                "schedule",
                "first event",
            )
        )
        explicit_static_route = (
            any(marker in text for marker in ("去公司", "to company", "to the office"))
            and any(marker in text for marker in ("路线", "route"))
            and not any(marker in text for marker in ("会议", "日程", "meeting", "schedule"))
        )
        return (
            has_morning
            and has_departure_or_route
            and not explicit_static_route
        ) or (
            has_morning
            and has_runtime_anchor
            and has_departure_or_route
            and not explicit_static_route
        )

    def _build_initial_calendar_task(self, user_input: str) -> Task:
        return Task(
            id=f"task-{uuid4()}",
            user_input=user_input,
            goal="Resolve tomorrow morning calendar context for departure planning.",
            status=TaskStatus.PLANNED,
            risk_level=RiskLevel.LOW,
            requires_confirmation=False,
            steps=[
                PlanStep(
                    id=f"step-{uuid4()}",
                    order=1,
                    description="Read tomorrow morning calendar events.",
                    tool_name="calendar_tool",
                    tool_call=ToolCall(
                        tool_name="calendar_tool",
                        arguments={
                            "date": "tomorrow",
                            "start_time": "06:00",
                            "end_time": "12:00",
                        },
                    ),
                )
            ],
        )

    def _select_earliest_event(
        self,
        observation: ToolObservation,
    ) -> dict | None:
        events = observation.result.get("events", [])
        if not events:
            return None
        return sorted(events, key=lambda event: event["start_time"])[0]

    def _prepare_side_effect(
        self,
        state: DynamicPlanningState,
    ) -> DynamicPlanningState:
        state.phase = DynamicPlanningPhase.SIDE_EFFECT_PLANNING
        try:
            proposal = self.notification_formatter.build_proposal(state)
        except NotificationGroundingError as exc:
            return self._fail(
                state,
                DynamicPlanningFailureType.NOTIFICATION_GROUNDING_ERROR,
                str(exc),
            )

        if proposal.tool_name != "notification_tool":
            return self._fail(
                state,
                DynamicPlanningFailureType.SIDE_EFFECT_PROPOSAL_ERROR,
                f"Unsupported side-effect tool: {proposal.tool_name}",
            )

        state.side_effect_proposal = proposal
        notification_task = Task(
            id=f"task-{uuid4()}",
            user_input=state.user_input,
            goal="Send authorized notification for completed dynamic result.",
            status=TaskStatus.PLANNED,
            risk_level=RiskLevel.LOW,
            requires_confirmation=False,
            steps=[
                PlanStep(
                    id=f"step-{uuid4()}",
                    order=1,
                    description="Send notification for dynamic result.",
                    tool_name=proposal.tool_name,
                    tool_call=ToolCall(
                        tool_name=proposal.tool_name,
                        arguments=proposal.arguments,
                    ),
                )
            ],
        )

        try:
            self.risk_policy.apply_to_task(notification_task)
        except UnknownToolRiskError as exc:
            return self._fail(
                state,
                DynamicPlanningFailureType.SIDE_EFFECT_RISK_POLICY_ERROR,
                str(exc),
            )

        self.confirmation_service.request_confirmation(notification_task)
        state.notification_task = notification_task
        state.side_effect_status = "pending_confirmation"
        state.phase = DynamicPlanningPhase.WAITING_CONFIRMATION
        state.final_result = self._build_final_result(state)
        return state

    def _validate_navigation_grounding(
        self,
        state: DynamicPlanningState,
        continuation_steps: list[PlanStep],
    ) -> str | None:
        if state.selected_event is None:
            return "Cannot validate navigation grounding without a selected event."

        expected_destination = state.selected_event.get("location")
        for step in continuation_steps:
            if step.tool_name != "navigation_tool" or step.tool_call is None:
                continue
            actual_destination = step.tool_call.arguments.get("destination")
            if actual_destination != expected_destination:
                return (
                    "navigation.destination must come from Calendar Observation "
                    f"location. expected={expected_destination}, actual={actual_destination}"
                )
        return None

    def _max_iterations_reached(self, state: DynamicPlanningState) -> bool:
        return state.iteration_count >= state.max_iterations

    def _notification_requested(self, user_input: str) -> bool:
        text = user_input.lower()
        markers = (
            "notify me",
            "notification",
            "tell me when ready",
            "after it is ready tell me",
            "提醒我",
            "通知",
            "告知",
            "告诉我",
        )
        return any(marker in text for marker in markers)

    def _has_scheduled_notification_request(self, user_input: str) -> bool:
        if not self._notification_requested(user_input):
            return False
        text = user_input.lower()
        if "提醒我" in text and any(
            marker in text for marker in ("安排", "出门", "通勤", "路线")
        ):
            return False
        markers = (
            "at 7",
            "tomorrow at",
            "later",
            "after 10 minutes",
            "10 minutes later",
            "七点",
            "十分钟后",
            "明早",
        )
        return any(marker in text for marker in markers) and not any(
            marker in text for marker in ("when ready", "准备好")
        )

    def _has_conditional_notification_request(self, user_input: str) -> bool:
        if not self._notification_requested(user_input):
            return False
        text = user_input.lower()
        markers = ("if ", "when it rains", "if it rains", "如果", "下雨", "堵车")
        return any(marker in text for marker in markers)

    def _fail(
        self,
        state: DynamicPlanningState,
        failure_type: DynamicPlanningFailureType,
        error: str,
    ) -> DynamicPlanningState:
        state.phase = DynamicPlanningPhase.FAILED
        state.failure_type = failure_type
        state.error = error
        if state.task is not None:
            state.task.status = TaskStatus.FAILED
        state.final_result = self._build_final_result(state)
        return state

    def _build_final_result(self, state: DynamicPlanningState) -> DynamicTaskResult:
        return DynamicTaskResult(
            status=state.phase,
            selected_event=state.selected_event,
            observations=state.observations,
            continuation_observations=state.continuation_observations,
            weather_result=self._result_for_tool(state, "weather_tool"),
            navigation_result=self._result_for_tool(state, "navigation_tool"),
            notification_task=state.notification_task,
            notification_result=state.notification_result,
            side_effect_status=state.side_effect_status,
            failure_type=state.failure_type,
            error=state.error,
        )

    def _result_for_tool(
        self,
        state: DynamicPlanningState,
        tool_name: str,
    ) -> dict | None:
        for observation in state.continuation_observations:
            if observation.tool_name == tool_name and observation.error is None:
                return observation.result
        return None
