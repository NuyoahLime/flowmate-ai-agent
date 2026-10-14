from flowmate.eval import DynamicNotificationEvaluator, load_dynamic_notification_dataset


def test_dynamic_notification_dataset_loads_with_expected_categories():
    cases = load_dynamic_notification_dataset("evals/dynamic_notification_v1.json")

    assert len(cases) == 12
    assert (
        sum(case.category == "dynamic_notification_confirm_success" for case in cases)
        == 4
    )
    assert sum(case.category == "dynamic_notification_reject" for case in cases) == 2
    assert sum(case.category == "dynamic_without_notification" for case in cases) == 2
    assert (
        sum(case.category == "scheduled_notification_unsupported" for case in cases)
        == 2
    )
    assert (
        sum(case.category == "conditional_notification_unsupported" for case in cases)
        == 2
    )


def test_dynamic_notification_evaluator_scores_confirm_case():
    case = next(
        item
        for item in load_dynamic_notification_dataset("evals/dynamic_notification_v1.json")
        if item.id == "dynamic-notification-confirm-001"
    )

    result = DynamicNotificationEvaluator().evaluate_case(case)

    assert result.notification_proposed is True
    assert result.pre_confirmation_blocked is True
    assert result.confirmed_success is True
    assert result.notification_executions == 1
    assert result.informational_reexecuted is False


def test_dynamic_notification_evaluator_scores_reject_case():
    case = next(
        item
        for item in load_dynamic_notification_dataset("evals/dynamic_notification_v1.json")
        if item.id == "dynamic-notification-reject-001"
    )

    result = DynamicNotificationEvaluator().evaluate_case(case)

    assert result.notification_proposed is True
    assert result.rejected_contained is True
    assert result.notification_executions == 0
    assert result.informational_reexecuted is False


def test_dynamic_notification_evaluator_scores_without_notification_case():
    case = next(
        item
        for item in load_dynamic_notification_dataset("evals/dynamic_notification_v1.json")
        if item.id == "dynamic-without-notification-001"
    )

    result = DynamicNotificationEvaluator().evaluate_case(case)

    assert result.notification_proposed is False
    assert result.side_effect_minimality_correct is True
    assert result.notification_executions == 0


def test_dynamic_notification_metrics_are_calculated():
    cases = load_dynamic_notification_dataset("evals/dynamic_notification_v1.json")

    results, metrics = DynamicNotificationEvaluator().evaluate_dataset(cases)

    assert results
    assert metrics.cases == 12
    assert metrics.side_effect_proposal_accuracy == 1.0
    assert metrics.pre_confirmation_blocking_rate == 1.0
    assert metrics.confirmed_side_effect_success_rate == 1.0
    assert metrics.rejected_side_effect_containment_rate == 1.0
    assert metrics.informational_reexecution_rate == 0.0
    assert metrics.notification_grounding_accuracy == 1.0
    assert metrics.side_effect_minimality_accuracy == 1.0
