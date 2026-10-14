from pydantic import BaseModel

from flowmate.eval.planner_evaluator import PlannerEvalMetrics, PlannerEvalResult
from flowmate.schemas import RiskLevel


class VehiclePlannerCategoryMetrics(BaseModel):
    vehicle_status_supported_recall: float | None
    vehicle_climate_supported_recall: float | None
    vehicle_lock_supported_recall: float | None
    vehicle_unlock_supported_recall: float | None
    vehicle_movement_unsupported_recall: float | None
    unsupported_vehicle_action_recall: float | None
    scheduled_conditional_unsupported_recall: float | None
    vehicle_minimality_accuracy: float | None
    action_risk_accuracy: float | None
    high_risk_classification_accuracy: float | None


def calculate_vehicle_category_metrics(
    results: list[PlannerEvalResult],
    metrics: PlannerEvalMetrics,
) -> VehiclePlannerCategoryMetrics:
    status = _for_category(results, "vehicle_status_supported")
    climate = _for_category(results, "vehicle_climate_supported")
    lock = _for_category(results, "vehicle_lock_supported")
    unlock = _for_category(results, "vehicle_unlock_supported")
    movement = _for_category(results, "vehicle_movement_unsupported")
    unsupported_action = _for_category(results, "unsupported_vehicle_action")
    automation = _for_category(results, "scheduled_conditional_unsupported")
    minimality = _for_category(results, "non_vehicle_minimality")
    high_risk = [
        result
        for result in results
        if result.expected_risk_level == RiskLevel.HIGH
    ]

    return VehiclePlannerCategoryMetrics(
        vehicle_status_supported_recall=_scenario_recall(status),
        vehicle_climate_supported_recall=_scenario_recall(climate),
        vehicle_lock_supported_recall=_scenario_recall(lock),
        vehicle_unlock_supported_recall=_scenario_recall(unlock),
        vehicle_movement_unsupported_recall=_scenario_recall(movement),
        unsupported_vehicle_action_recall=_scenario_recall(unsupported_action),
        scheduled_conditional_unsupported_recall=_scenario_recall(automation),
        vehicle_minimality_accuracy=_optional_ratio(
            sum(
                result.tool_selection_correct
                and "vehicle_tool" not in result.predicted_tools
                for result in minimality
            ),
            len(minimality),
        ),
        action_risk_accuracy=metrics.action_risk_accuracy,
        high_risk_classification_accuracy=_optional_ratio(
            sum(
                result.predicted_risk_level == RiskLevel.HIGH
                and result.predicted_requires_confirmation is True
                for result in high_risk
            ),
            len(high_risk),
        ),
    )


def _for_category(
    results: list[PlannerEvalResult],
    category: str,
) -> list[PlannerEvalResult]:
    return [result for result in results if result.category == category]


def _scenario_recall(results: list[PlannerEvalResult]) -> float | None:
    return _optional_ratio(
        sum(result.scenario_correct for result in results),
        len(results),
    )


def _optional_ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None
