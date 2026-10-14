import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flowmate.agent import (
    LLMClientConfig,
    LLMClientConfigurationError,
    LLMPlanner,
    LLMProviderError,
    OpenAILLMClient,
    PlannerOutputValidationError,
    UnsupportedPlanningScenarioError,
)


MORNING_COMMUTE_INPUT = "我明天早上八点半要去公司开会，帮我安排一下明早出门。"
UNSUPPORTED_INPUT = "帮我把客厅灯关掉"


def main() -> None:
    try:
        config = LLMClientConfig.from_env()
        planner = LLMPlanner(OpenAILLMClient(config))
    except LLMClientConfigurationError as exc:
        print(f"Missing configuration: {exc}")
        return
    except LLMProviderError as exc:
        print(f"Provider setup failed: {exc}")
        return

    print("user_input:")
    print(MORNING_COMMUTE_INPUT)
    try:
        task = planner.plan(MORNING_COMMUTE_INPUT)
        print("task_json:")
        print(json.dumps(task.model_dump(mode="json"), ensure_ascii=False, indent=2))
    except (
        LLMProviderError,
        PlannerOutputValidationError,
        UnsupportedPlanningScenarioError,
    ) as exc:
        print(f"planning_failed: {exc}")

    print("unsupported_user_input:")
    print(UNSUPPORTED_INPUT)
    try:
        planner.plan(UNSUPPORTED_INPUT)
        print("unsupported_result: unexpected task generated")
    except UnsupportedPlanningScenarioError as exc:
        print(f"unsupported_result: {exc}")
    except (LLMProviderError, PlannerOutputValidationError) as exc:
        print(f"unsupported_provider_failed: {exc}")


if __name__ == "__main__":
    main()
