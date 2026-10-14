from flowmate.eval.proactive_trigger_evaluator import (
    ProactiveTriggerEvaluator,
    load_proactive_trigger_eval_dataset,
)


def test_proactive_trigger_eval_dataset_loads():
    cases = load_proactive_trigger_eval_dataset("evals/proactive_trigger_eval_v1.json")

    assert len(cases) == 12


def test_proactive_trigger_evaluator_metrics_are_deterministic():
    cases = load_proactive_trigger_eval_dataset("evals/proactive_trigger_eval_v1.json")
    _, metrics = ProactiveTriggerEvaluator().evaluate_dataset(cases)

    assert metrics.registration_accuracy == 1.0
    assert metrics.due_detection_accuracy == 1.0
    assert metrics.expiration_accuracy == 1.0
    assert metrics.duplicate_trigger_prevention == 1.0
    assert metrics.duplicate_fire_prevention == 1.0
    assert metrics.restart_idempotency == 1.0
    assert metrics.task_creation_accuracy == 1.0
    assert metrics.side_effect_containment == 1.0
