import json
from pathlib import Path
from typing import Any, Iterable

from pydantic import BaseModel, Field

from flowmate.agent.llm_client import LLMProviderError
from flowmate.agent.planner import (
    Planner,
    PlannerOutputValidationError,
    UnsupportedPlanningScenarioError,
)
from flowmate.agent.tool_argument_validator import ToolArgumentValidationError
from flowmate.schemas import RiskLevel, Task


class PlannerEvalCase(BaseModel):
    id: str
    user_input: str
    supported: bool
    expected_tools: list[str] = Field(default_factory=list)
    expected_arguments: dict[str, dict[str, Any]] = Field(default_factory=dict)
    category: str
    expected_risk_level: RiskLevel | None = None
    expected_requires_confirmation: bool | None = None


class PlannerEvalResult(BaseModel):
    case_id: str
    category: str
    failure_type: str | None = None
    planner_name: str
    user_input: str
    expected_supported: bool
    predicted_supported: bool
    scenario_correct: bool
    tool_selection_correct: bool
    parameter_accuracy: float | None
    parameter_completeness: float | None
    temporal_constraint_preserved: bool | None = None
    schema_valid: bool
    expected_tools: list[str]
    expected_arguments: dict[str, dict[str, Any]]
    predicted_tools: list[str] = Field(default_factory=list)
    predicted_arguments: dict[str, dict[str, Any]] = Field(default_factory=dict)
    expected_risk_level: RiskLevel | None = None
    expected_requires_confirmation: bool | None = None
    predicted_risk_level: RiskLevel | None = None
    predicted_requires_confirmation: bool | None = None
    risk_assessment_correct: bool | None = None
    extra_tool_case: bool = False
    error: str | None = None
    failure_stage: str | None = None
    provider_error_type: str | None = None
    attempt_count: int = 1
    retry_performed: bool = False
    first_provider_error_type: str | None = None
    final_provider_error_type: str | None = None


class PlannerEvalMetrics(BaseModel):
    cases: int
    scenario_accuracy: float
    supported_recall: float | None
    unsupported_recall: float | None
    tool_selection_accuracy: float
    parameter_accuracy: float
    parameter_completeness: float | None
    temporal_constraint_preservation_rate: float | None = None
    unsupported_accuracy: float | None
    schema_valid_rate: float
    extra_tool_rate: float
    retry_cases: int = 0
    retry_recovery_rate: float | None = None
    total_provider_attempts: int = 0
    average_provider_attempts_per_case: float = 0.0
    action_risk_accuracy: float | None = None


class PlannerEvaluator:
    def evaluate_case(
        self,
        planner: Planner,
        case: PlannerEvalCase,
        planner_name: str | None = None,
    ) -> PlannerEvalResult:
        name = planner_name or planner.__class__.__name__

        try:
            output = planner.plan(case.user_input)
        except UnsupportedPlanningScenarioError as exc:
            retry_metadata = self._extract_retry_metadata(planner)
            return PlannerEvalResult(
                case_id=case.id,
                category=case.category,
                failure_type=None if case.supported is False else "scenario_error",
                planner_name=name,
                user_input=case.user_input,
                expected_supported=case.supported,
                predicted_supported=False,
                scenario_correct=case.supported is False,
                tool_selection_correct=case.supported is False and not case.expected_tools,
                parameter_accuracy=None,
                parameter_completeness=None,
                temporal_constraint_preserved=self._temporal_constraint_preserved(
                    case.expected_arguments,
                    {},
                ),
                schema_valid=case.supported is False,
                expected_tools=case.expected_tools,
                expected_arguments=case.expected_arguments,
                error=str(exc),
                failure_stage="capability_or_unsupported",
                **self._risk_result_fields(case),
                **retry_metadata,
            )
        except ToolArgumentValidationError as exc:
            return self._parameter_validation_result(
                case,
                name,
                exc,
                self._extract_retry_metadata(planner),
            )
        except PlannerOutputValidationError as exc:
            return self._llm_schema_error_result(
                case,
                name,
                exc,
                self._extract_retry_metadata(planner),
            )
        except Exception as exc:
            return self._error_result(
                case,
                name,
                exc,
                self._extract_retry_metadata(planner),
            )

        if not isinstance(output, Task):
            return self._error_result(
                case,
                name,
                "Planner did not return a Task.",
                self._extract_retry_metadata(planner),
            )

        predicted_tools, predicted_arguments = self._extract_task_details(output)
        tool_selection_correct = sorted(predicted_tools) == sorted(case.expected_tools)
        parameter_accuracy = self._parameter_accuracy(
            case.expected_arguments,
            predicted_arguments,
        )
        parameter_completeness = self._parameter_completeness(
            case.expected_arguments,
            predicted_arguments,
        )
        temporal_constraint_preserved = self._temporal_constraint_preserved(
            case.expected_arguments,
            predicted_arguments,
        )
        scenario_correct = case.supported is True
        extra_tool_case = case.supported and any(
            tool_name not in case.expected_tools for tool_name in predicted_tools
        )
        failure_type = None
        if not scenario_correct:
            failure_type = "scenario_error"
        elif not tool_selection_correct:
            failure_type = "tool_selection_error"
        elif parameter_completeness < 1.0:
            failure_type = "parameter_completeness_error"
        elif parameter_accuracy < 1.0:
            failure_type = "parameter_value_error"

        return PlannerEvalResult(
            case_id=case.id,
            category=case.category,
            failure_type=failure_type,
            planner_name=name,
            user_input=case.user_input,
            expected_supported=case.supported,
            predicted_supported=True,
            scenario_correct=scenario_correct,
            tool_selection_correct=tool_selection_correct,
            parameter_accuracy=parameter_accuracy,
            parameter_completeness=parameter_completeness,
            temporal_constraint_preserved=temporal_constraint_preserved,
            schema_valid=True,
            expected_tools=case.expected_tools,
            expected_arguments=case.expected_arguments,
            predicted_tools=predicted_tools,
            predicted_arguments=predicted_arguments,
            extra_tool_case=extra_tool_case,
            **self._risk_result_fields(case, output),
            **self._extract_retry_metadata(planner),
        )

    def evaluate_dataset(
        self,
        planner: Planner,
        cases: Iterable[PlannerEvalCase],
        planner_name: str | None = None,
    ) -> tuple[list[PlannerEvalResult], PlannerEvalMetrics]:
        results = [
            self.evaluate_case(planner, case, planner_name=planner_name)
            for case in cases
        ]
        return results, self.calculate_metrics(results)

    def calculate_metrics(
        self,
        results: list[PlannerEvalResult],
    ) -> PlannerEvalMetrics:
        total = len(results)
        supported_results = [result for result in results if result.expected_supported]
        unsupported_results = [
            result for result in results if not result.expected_supported
        ]

        return PlannerEvalMetrics(
            cases=total,
            scenario_accuracy=self._ratio(
                sum(result.scenario_correct for result in results),
                total,
            ),
            supported_recall=self._optional_ratio(
                sum(result.scenario_correct for result in supported_results),
                len(supported_results),
            ),
            unsupported_recall=self._optional_ratio(
                sum(result.scenario_correct for result in unsupported_results),
                len(unsupported_results),
            ),
            tool_selection_accuracy=self._ratio(
                sum(result.tool_selection_correct for result in supported_results),
                len(supported_results),
            ),
            parameter_accuracy=self._average_parameter_accuracy(supported_results),
            parameter_completeness=self._average_parameter_completeness(supported_results),
            temporal_constraint_preservation_rate=(
                self._temporal_constraint_preservation_rate(results)
            ),
            unsupported_accuracy=self._optional_ratio(
                sum(result.scenario_correct for result in unsupported_results),
                len(unsupported_results),
            ),
            schema_valid_rate=self._ratio(
                sum(result.schema_valid for result in results),
                total,
            ),
            extra_tool_rate=self._ratio(
                sum(result.extra_tool_case for result in supported_results),
                len(supported_results),
            ),
            retry_cases=sum(result.retry_performed for result in results),
            retry_recovery_rate=self._retry_recovery_rate(results),
            total_provider_attempts=sum(result.attempt_count for result in results),
            average_provider_attempts_per_case=self._ratio(
                sum(result.attempt_count for result in results),
                total,
            ),
            action_risk_accuracy=self._action_risk_accuracy(results),
        )

    def _extract_task_details(
        self,
        task: Task,
    ) -> tuple[list[str], dict[str, dict[str, Any]]]:
        tools = [step.tool_name for step in task.steps]
        arguments = {
            step.tool_name: dict(step.tool_call.arguments)
            for step in task.steps
            if step.tool_call is not None
        }
        return tools, arguments

    def _parameter_accuracy(
        self,
        expected: dict[str, dict[str, Any]],
        predicted: dict[str, dict[str, Any]],
    ) -> float:
        expected_fields = [
            (tool_name, field_name, expected_value)
            for tool_name, arguments in expected.items()
            for field_name, expected_value in arguments.items()
        ]
        if not expected_fields:
            return 1.0

        correct = sum(
            predicted.get(tool_name, {}).get(field_name) == expected_value
            for tool_name, field_name, expected_value in expected_fields
        )
        return correct / len(expected_fields)

    def _parameter_completeness(
        self,
        expected: dict[str, dict[str, Any]],
        predicted: dict[str, dict[str, Any]],
    ) -> float | None:
        expected_fields = [
            (tool_name, field_name)
            for tool_name, arguments in expected.items()
            for field_name in arguments
        ]
        if not expected_fields:
            return None

        present = sum(
            field_name in predicted.get(tool_name, {})
            for tool_name, field_name in expected_fields
        )
        return present / len(expected_fields)

    def _average_parameter_accuracy(
        self,
        results: list[PlannerEvalResult],
    ) -> float:
        if not results:
            return 0.0
        return sum(result.parameter_accuracy or 0.0 for result in results) / len(results)

    def _average_parameter_completeness(
        self,
        results: list[PlannerEvalResult],
    ) -> float | None:
        applicable_scores = [
            result.parameter_completeness
            for result in results
            if result.parameter_completeness is not None
        ]
        if not applicable_scores:
            return None
        return sum(applicable_scores) / len(applicable_scores)

    def _error_result(
        self,
        case: PlannerEvalCase,
        planner_name: str,
        error: Exception | str,
        retry_metadata: dict[str, Any] | None = None,
    ) -> PlannerEvalResult:
        error_text = str(error)
        failure_type = error.error_type if isinstance(error, LLMProviderError) else "schema_error"
        failure_stage = error.stage if isinstance(error, LLMProviderError) else "task_construction"

        return PlannerEvalResult(
            case_id=case.id,
            category=case.category,
            failure_type=failure_type,
            planner_name=planner_name,
            user_input=case.user_input,
            expected_supported=case.supported,
            predicted_supported=False,
            scenario_correct=False,
            tool_selection_correct=False,
            parameter_accuracy=None,
            parameter_completeness=None,
            temporal_constraint_preserved=self._temporal_constraint_preserved(
                case.expected_arguments,
                {},
            ),
            schema_valid=False,
            expected_tools=case.expected_tools,
            expected_arguments=case.expected_arguments,
            error=error_text,
            failure_stage=failure_stage,
            provider_error_type=error.error_type if isinstance(error, LLMProviderError) else None,
            **self._risk_result_fields(case),
            **(retry_metadata or {}),
        )

    def _parameter_validation_result(
        self,
        case: PlannerEvalCase,
        planner_name: str,
        error: ToolArgumentValidationError,
        retry_metadata: dict[str, Any] | None = None,
    ) -> PlannerEvalResult:
        predicted_tools = error.predicted_tools
        predicted_arguments = error.predicted_arguments
        scenario_correct = case.supported is True
        tool_selection_correct = sorted(predicted_tools) == sorted(case.expected_tools)

        return PlannerEvalResult(
            case_id=case.id,
            category=case.category,
            failure_type="tool_argument_validation_error",
            planner_name=planner_name,
            user_input=case.user_input,
            expected_supported=case.supported,
            predicted_supported=True,
            scenario_correct=scenario_correct,
            tool_selection_correct=tool_selection_correct,
            parameter_accuracy=self._parameter_accuracy(
                case.expected_arguments,
                predicted_arguments,
            ),
            parameter_completeness=self._parameter_completeness(
                case.expected_arguments,
                predicted_arguments,
            ),
            temporal_constraint_preserved=self._temporal_constraint_preserved(
                case.expected_arguments,
                predicted_arguments,
            ),
            schema_valid=False,
            expected_tools=case.expected_tools,
            expected_arguments=case.expected_arguments,
            predicted_tools=predicted_tools,
            predicted_arguments=predicted_arguments,
            extra_tool_case=case.supported and any(
                tool_name not in case.expected_tools for tool_name in predicted_tools
            ),
            error=str(error),
            failure_stage="tool_argument_validation",
            **self._risk_result_fields(case),
            **(retry_metadata or {}),
        )

    def _llm_schema_error_result(
        self,
        case: PlannerEvalCase,
        planner_name: str,
        error: PlannerOutputValidationError,
        retry_metadata: dict[str, Any] | None = None,
    ) -> PlannerEvalResult:
        return PlannerEvalResult(
            case_id=case.id,
            category=case.category,
            failure_type="llm_schema_error",
            planner_name=planner_name,
            user_input=case.user_input,
            expected_supported=case.supported,
            predicted_supported=False,
            scenario_correct=False,
            tool_selection_correct=False,
            parameter_accuracy=None,
            parameter_completeness=None,
            temporal_constraint_preserved=self._temporal_constraint_preserved(
                case.expected_arguments,
                {},
            ),
            schema_valid=False,
            expected_tools=case.expected_tools,
            expected_arguments=case.expected_arguments,
            error=str(error),
            failure_stage="llm_plan_validation",
            **self._risk_result_fields(case),
            **(retry_metadata or {}),
        )

    def _ratio(self, numerator: int, denominator: int) -> float:
        return numerator / denominator if denominator else 0.0

    def _optional_ratio(self, numerator: int, denominator: int) -> float | None:
        return numerator / denominator if denominator else None

    def _temporal_constraint_preserved(
        self,
        expected: dict[str, dict[str, Any]],
        predicted: dict[str, dict[str, Any]],
    ) -> bool | None:
        expected_calendar_arguments = expected.get("calendar_tool")
        if not expected_calendar_arguments:
            return None

        if (
            "start_time" not in expected_calendar_arguments
            or "end_time" not in expected_calendar_arguments
        ):
            return None

        predicted_calendar_arguments = predicted.get("calendar_tool", {})
        return (
            predicted_calendar_arguments.get("start_time")
            == expected_calendar_arguments["start_time"]
            and predicted_calendar_arguments.get("end_time")
            == expected_calendar_arguments["end_time"]
        )

    def _temporal_constraint_preservation_rate(
        self,
        results: list[PlannerEvalResult],
    ) -> float | None:
        applicable_results = [
            result
            for result in results
            if result.temporal_constraint_preserved is not None
        ]
        if not applicable_results:
            return None

        return sum(
            result.temporal_constraint_preserved for result in applicable_results
        ) / len(applicable_results)

    def _extract_retry_metadata(self, planner: Planner) -> dict[str, Any]:
        client = getattr(planner, "client", None)
        metadata = getattr(client, "last_call_metadata", None)
        if metadata is None:
            return {}

        return {
            "attempt_count": metadata.attempt_count or 1,
            "retry_performed": metadata.retry_performed,
            "first_provider_error_type": metadata.first_provider_error_type,
            "final_provider_error_type": metadata.final_provider_error_type,
        }

    def _retry_recovery_rate(
        self,
        results: list[PlannerEvalResult],
    ) -> float | None:
        retry_results = [result for result in results if result.retry_performed]
        if not retry_results:
            return None

        recovered = sum(self._result_successful(result) for result in retry_results)
        return recovered / len(retry_results)

    def _result_successful(self, result: PlannerEvalResult) -> bool:
        return (
            result.scenario_correct
            and result.tool_selection_correct
            and (result.parameter_accuracy is None or result.parameter_accuracy == 1.0)
            and (
                result.parameter_completeness is None
                or result.parameter_completeness == 1.0
            )
            and result.schema_valid
        )

    def _risk_result_fields(
        self,
        case: PlannerEvalCase,
        task: Task | None = None,
    ) -> dict[str, Any]:
        applicable = (
            case.expected_risk_level is not None
            and case.expected_requires_confirmation is not None
        )
        if not applicable:
            return {}

        predicted_risk_level = task.risk_level if task is not None else None
        predicted_requires_confirmation = (
            task.requires_confirmation if task is not None else None
        )
        return {
            "expected_risk_level": case.expected_risk_level,
            "expected_requires_confirmation": case.expected_requires_confirmation,
            "predicted_risk_level": predicted_risk_level,
            "predicted_requires_confirmation": predicted_requires_confirmation,
            "risk_assessment_correct": (
                predicted_risk_level == case.expected_risk_level
                and predicted_requires_confirmation
                == case.expected_requires_confirmation
            ),
        }

    def _action_risk_accuracy(
        self,
        results: list[PlannerEvalResult],
    ) -> float | None:
        applicable = [
            result
            for result in results
            if result.expected_risk_level is not None
            and result.expected_requires_confirmation is not None
        ]
        return self._optional_ratio(
            sum(result.risk_assessment_correct is True for result in applicable),
            len(applicable),
        )


def load_eval_dataset(path: str | Path) -> list[PlannerEvalCase]:
    with Path(path).open("r", encoding="utf-8") as file:
        raw_cases = json.load(file)
    return [PlannerEvalCase.model_validate(case) for case in raw_cases]
