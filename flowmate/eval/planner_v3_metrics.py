from pydantic import BaseModel

from flowmate.eval.planner_evaluator import PlannerEvalResult


class PlannerV3CapabilityMetrics(BaseModel):
    current_capability_accuracy: float
    weather_supported_recall: float | None
    navigation_supported_recall: float | None
    calendar_supported_recall: float | None
    notification_supported_recall: float | None
    smart_home_supported_recall: float | None
    vehicle_supported_recall: float | None
    scheduled_automation_unsupported_recall: float | None
    conditional_automation_unsupported_recall: float | None
    unsupported_smart_home_recall: float | None
    unsupported_vehicle_movement_recall: float | None
    unsupported_vehicle_action_or_telemetry_recall: float | None
    calendar_write_unsupported_recall: float | None


def calculate_planner_v3_capability_metrics(
    results: list[PlannerEvalResult],
) -> PlannerV3CapabilityMetrics:
    return PlannerV3CapabilityMetrics(
        current_capability_accuracy=_ratio(
            sum(result.scenario_correct for result in results),
            len(results),
        ),
        weather_supported_recall=_category_recall(results, "weather_supported"),
        navigation_supported_recall=_category_recall(
            results,
            "navigation_supported",
        ),
        calendar_supported_recall=_category_recall(
            results,
            "calendar_read_supported",
        ),
        notification_supported_recall=_category_recall(
            results,
            "notification_immediate_supported",
        ),
        smart_home_supported_recall=_category_recall(
            results,
            "smart_home_supported",
        ),
        vehicle_supported_recall=_category_recall(results, "vehicle_supported"),
        scheduled_automation_unsupported_recall=_category_recall(
            results,
            "scheduled_automation_unsupported",
        ),
        conditional_automation_unsupported_recall=_category_recall(
            results,
            "conditional_automation_unsupported",
        ),
        unsupported_smart_home_recall=_category_recall(
            results,
            "unsupported_smart_home",
        ),
        unsupported_vehicle_movement_recall=_category_recall(
            results,
            "unsupported_vehicle_movement",
        ),
        unsupported_vehicle_action_or_telemetry_recall=_category_recall(
            results,
            "unsupported_vehicle_action_or_telemetry",
        ),
        calendar_write_unsupported_recall=_category_recall(
            results,
            "calendar_write_unsupported",
        ),
    )


def _category_recall(
    results: list[PlannerEvalResult],
    category: str,
) -> float | None:
    category_results = [result for result in results if result.category == category]
    if not category_results:
        return None
    return sum(result.scenario_correct for result in category_results) / len(
        category_results
    )


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0
