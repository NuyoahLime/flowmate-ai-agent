from typing import Any, Mapping

import pytest

from flowmate.agent import (
    LLMPlanner,
    LLMProviderError,
    RetryingLLMClient,
    RetryPolicy,
    ToolArgumentValidationError,
    UnsupportedPlanningScenarioError,
)
from flowmate.eval import PlannerEvaluator
from tests.test_llm_planner import USER_INPUT, valid_llm_output
from tests.test_planner_evaluator import supported_case


class SequenceLLMClient:
    def __init__(self, outputs: list[Mapping[str, Any] | Exception]) -> None:
        self.outputs = outputs
        self.call_count = 0

    def generate_plan(self, user_input: str, system_prompt: str) -> Mapping[str, Any]:
        output = self.outputs[self.call_count]
        self.call_count += 1
        if isinstance(output, Exception):
            raise output
        return output


def provider_error(error_type: str) -> LLMProviderError:
    return LLMProviderError(
        f"{error_type} occurred",
        stage="test_stage",
        error_type=error_type,
    )


def unsupported_output() -> dict[str, Any]:
    return {
        "unsupported": True,
        "reason": "Current tools cannot satisfy this request.",
        "plan": None,
    }


def invalid_schema_output() -> dict[str, Any]:
    return {"unsupported": False, "reason": None, "plan": None}


def invalid_tool_arguments_output() -> dict[str, Any]:
    output = valid_llm_output()
    del output["plan"]["steps"][0]["arguments"]["departure_time"]
    return output


def matching_supported_case_output() -> dict[str, Any]:
    output = valid_llm_output()
    output["plan"]["steps"][0]["arguments"]["departure_time"] = (
        "tomorrow morning"
    )
    return output


def test_retry_policy_allows_retryable_provider_errors():
    policy = RetryPolicy()

    assert policy.is_retryable(provider_error("provider_empty_output")) is True
    assert policy.is_retryable(provider_error("provider_transport_error")) is True
    assert policy.is_retryable(provider_error("provider_invalid_json")) is True
    assert policy.is_retryable(provider_error("provider_parse_error")) is True


def test_retry_policy_rejects_non_retryable_provider_errors():
    policy = RetryPolicy()

    assert policy.is_retryable(provider_error("llm_schema_error")) is False
    assert policy.is_retryable(RuntimeError("not provider")) is False


def test_first_attempt_success_does_not_retry():
    inner = SequenceLLMClient([valid_llm_output()])
    client = RetryingLLMClient(inner)

    output = client.generate_plan(USER_INPUT, "prompt")

    assert output["unsupported"] is False
    assert inner.call_count == 1
    assert client.last_call_metadata.attempt_count == 1
    assert client.last_call_metadata.retry_performed is False


@pytest.mark.parametrize(
    "error_type",
    [
        "provider_empty_output",
        "provider_transport_error",
        "provider_invalid_json",
        "provider_parse_error",
    ],
)
def test_retryable_provider_error_can_recover_on_second_attempt(error_type: str):
    inner = SequenceLLMClient([provider_error(error_type), valid_llm_output()])
    client = RetryingLLMClient(inner)

    output = client.generate_plan(USER_INPUT, "prompt")

    assert output["unsupported"] is False
    assert inner.call_count == 2
    assert client.last_call_metadata.attempt_count == 2
    assert client.last_call_metadata.retry_performed is True
    assert client.last_call_metadata.first_provider_error_type == error_type
    assert client.last_call_metadata.final_provider_error_type is None


def test_retryable_provider_error_exhausts_after_second_attempt():
    inner = SequenceLLMClient(
        [
            provider_error("provider_empty_output"),
            provider_error("provider_invalid_json"),
            valid_llm_output(),
        ]
    )
    client = RetryingLLMClient(inner)

    with pytest.raises(LLMProviderError):
        client.generate_plan(USER_INPUT, "prompt")

    assert inner.call_count == 2
    assert client.last_call_metadata.attempt_count == 2
    assert client.last_call_metadata.retry_performed is True
    assert client.last_call_metadata.first_provider_error_type == "provider_empty_output"
    assert client.last_call_metadata.final_provider_error_type == "provider_invalid_json"


def test_llm_schema_error_is_not_retried():
    inner = SequenceLLMClient([invalid_schema_output(), valid_llm_output()])
    planner = LLMPlanner(RetryingLLMClient(inner))

    with pytest.raises(Exception):
        planner.plan(USER_INPUT)

    assert inner.call_count == 1


def test_semantic_unsupported_is_not_retried():
    inner = SequenceLLMClient([unsupported_output(), valid_llm_output()])
    planner = LLMPlanner(RetryingLLMClient(inner))

    with pytest.raises(UnsupportedPlanningScenarioError):
        planner.plan(USER_INPUT)

    assert inner.call_count == 1


def test_tool_argument_validation_error_is_not_retried():
    inner = SequenceLLMClient([invalid_tool_arguments_output(), valid_llm_output()])
    planner = LLMPlanner(RetryingLLMClient(inner))

    with pytest.raises(ToolArgumentValidationError):
        planner.plan(USER_INPUT)

    assert inner.call_count == 1


def test_retry_metadata_enters_eval_result():
    inner = SequenceLLMClient([provider_error("provider_empty_output"), valid_llm_output()])
    planner = LLMPlanner(RetryingLLMClient(inner))

    result = PlannerEvaluator().evaluate_case(planner, supported_case())

    assert result.retry_performed is True
    assert result.attempt_count == 2
    assert result.first_provider_error_type == "provider_empty_output"


def test_retry_recovery_rate_is_calculated():
    evaluator = PlannerEvaluator()
    output = matching_supported_case_output()
    retry_recovered = evaluator.evaluate_case(
        LLMPlanner(
            RetryingLLMClient(
                SequenceLLMClient([provider_error("provider_empty_output"), output])
            )
        ),
        supported_case(),
    )
    no_retry = evaluator.evaluate_case(
        LLMPlanner(RetryingLLMClient(SequenceLLMClient([output]))),
        supported_case(),
    )

    metrics = evaluator.calculate_metrics([retry_recovered, no_retry])

    assert metrics.retry_cases == 1
    assert metrics.retry_recovery_rate == 1.0
    assert metrics.total_provider_attempts == 3
    assert metrics.average_provider_attempts_per_case == 1.5


def test_retry_recovery_rate_is_not_applicable_without_retry_cases():
    result = PlannerEvaluator().evaluate_case(
        LLMPlanner(RetryingLLMClient(SequenceLLMClient([valid_llm_output()]))),
        supported_case(),
    )

    metrics = PlannerEvaluator().calculate_metrics([result])

    assert metrics.retry_cases == 0
    assert metrics.retry_recovery_rate is None


def test_api_key_is_not_in_retry_error_message():
    inner = SequenceLLMClient([provider_error("provider_empty_output")])
    client = RetryingLLMClient(inner, max_attempts=1)

    with pytest.raises(LLMProviderError) as exc_info:
        client.generate_plan(USER_INPUT, "prompt")

    assert "test-secret-key" not in str(exc_info.value)
