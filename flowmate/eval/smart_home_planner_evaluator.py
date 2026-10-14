from pydantic import BaseModel

from flowmate.eval.planner_evaluator import PlannerEvalMetrics, PlannerEvalResult


class SmartHomePlannerCategoryMetrics(BaseModel):
    smart_home_supported_recall: float | None
    unsupported_device_recall: float | None
    scheduled_automation_unsupported_recall: float | None
    conditional_automation_unsupported_recall: float | None
    smart_home_minimality_accuracy: float | None
    action_risk_accuracy: float | None


def calculate_smart_home_category_metrics(
    results: list[PlannerEvalResult],
    metrics: PlannerEvalMetrics,
) -> SmartHomePlannerCategoryMetrics:
    smart_home_supported = _for_categories(
        results,
        {"light_control_supported", "air_conditioner_control_supported"},
    )
    unsupported_devices = _for_categories(results, {"unsupported_device"})
    scheduled = _for_categories(results, {"scheduled_automation_unsupported"})
    conditional = _for_categories(results, {"conditional_automation_unsupported"})
    minimality = _for_categories(results, {"non_smart_home_minimality"})

    return SmartHomePlannerCategoryMetrics(
        smart_home_supported_recall=_optional_ratio(
            sum(result.scenario_correct for result in smart_home_supported),
            len(smart_home_supported),
        ),
        unsupported_device_recall=_optional_ratio(
            sum(result.scenario_correct for result in unsupported_devices),
            len(unsupported_devices),
        ),
        scheduled_automation_unsupported_recall=_optional_ratio(
            sum(result.scenario_correct for result in scheduled),
            len(scheduled),
        ),
        conditional_automation_unsupported_recall=_optional_ratio(
            sum(result.scenario_correct for result in conditional),
            len(conditional),
        ),
        smart_home_minimality_accuracy=_optional_ratio(
            sum(
                result.tool_selection_correct
                and "smart_home_tool" not in result.predicted_tools
                for result in minimality
            ),
            len(minimality),
        ),
        action_risk_accuracy=metrics.action_risk_accuracy,
    )


def _for_categories(
    results: list[PlannerEvalResult],
    categories: set[str],
) -> list[PlannerEvalResult]:
    return [result for result in results if result.category in categories]


def _optional_ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None
