from datetime import datetime

from fastapi.testclient import TestClient

from flowmate.triggers import (
    CalendarTriggerRegistrationService,
    CalendarTriggerSourceEvent,
    SQLiteTriggerRepository,
)


def client_with_demo_db(monkeypatch, tmp_path):
    monkeypatch.setenv("FLOWMATE_DB_PATH", str(tmp_path / "flowmate_stage27.db"))
    monkeypatch.setenv("FLOWMATE_DEMO_MODE", "true")
    from main import app

    return TestClient(app)


def test_system_status_api(monkeypatch, tmp_path):
    client = client_with_demo_db(monkeypatch, tmp_path)

    response = client.get("/api/v1/system/status")

    assert response.status_code == 200
    body = response.json()
    assert body["backend_ready"] is True
    assert body["database_ready"] is True
    assert body["demo_mode"] is True
    assert body["providers"]["notification"] == "Mock"
    assert body["integrations"]["feishu"]["status"] == "engineering_ready_real_pending"


def test_eval_api_returns_historical_saved_snapshot(monkeypatch, tmp_path):
    client = client_with_demo_db(monkeypatch, tmp_path)

    response = client.get("/api/v1/evals")

    assert response.status_code == 200
    body = response.json()
    planner_snapshot = body["planner_v3"]
    assert planner_snapshot["metrics"]["cases"] == 36
    assert len(planner_snapshot["results"]) == 36
    assert (
        planner_snapshot["metrics"]["scenario_accuracy"]
        == 0.9722222222222222
    )
    assert body["proactive_trigger_v1"]["metrics"]["side_effect_containment"] == 1.0


def test_demo_morning_commute_creates_trace_and_pending_notification(monkeypatch, tmp_path):
    client = client_with_demo_db(monkeypatch, tmp_path)

    response = client.post(
        "/api/v1/demo/tasks",
        json={
            "scenario": "morning_commute",
            "user_input": "明早 8:30 公司开会，帮我安排好出门并提醒我。",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["task"]["status"] == "COMPLETED"
    assert body["dynamic_state"]["selected_event"]["location"] == "人民广场"
    assert body["notification_task"]["requires_confirmation"] is True
    assert body["notification_task"]["confirmation_status"] == "PENDING"
    assert body["notification_task"]["status"] == "WAITING_CONFIRMATION"
    assert body["notification_task"]["steps"][0]["tool_call"]["status"] == "PENDING"


def test_confirm_api_uses_confirmation_and_executor(monkeypatch, tmp_path):
    client = client_with_demo_db(monkeypatch, tmp_path)
    created = client.post(
        "/api/v1/demo/tasks",
        json={
            "scenario": "morning_commute",
            "user_input": "明早 8:30 公司开会，帮我安排好出门并提醒我。",
        },
    ).json()
    notification_task_id = created["notification_task"]["id"]

    response = client.post(f"/api/v1/tasks/{notification_task_id}/confirm")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["confirmation_status"] == "CONFIRMED"
    assert body["steps"][0]["tool_call"]["status"] == "SUCCESS"
    assert body["steps"][0]["tool_call"]["result"]["status"] == "mock_delivered"


def test_reject_api_contains_side_effect(monkeypatch, tmp_path):
    client = client_with_demo_db(monkeypatch, tmp_path)
    created = client.post(
        "/api/v1/demo/tasks",
        json={
            "scenario": "morning_commute",
            "user_input": "明早 8:30 公司开会，帮我安排好出门并提醒我。",
        },
    ).json()
    notification_task_id = created["notification_task"]["id"]

    response = client.post(f"/api/v1/tasks/{notification_task_id}/reject")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "CANCELLED"
    assert body["confirmation_status"] == "REJECTED"
    assert body["steps"][0]["tool_call"]["status"] == "PENDING"
    assert body["steps"][0]["tool_call"]["result"] is None


def test_vehicle_safety_demo_is_high_risk_pending(monkeypatch, tmp_path):
    client = client_with_demo_db(monkeypatch, tmp_path)

    response = client.post(
        "/api/v1/demo/tasks",
        json={"scenario": "vehicle_safety", "user_input": "解锁我的车"},
    )

    assert response.status_code == 200
    task = response.json()["task"]
    assert task["risk_level"] == "HIGH"
    assert task["requires_confirmation"] is True
    assert task["confirmation_status"] == "PENDING"
    assert task["steps"][0]["tool_call"]["status"] == "PENDING"


def test_smart_home_demo_is_medium_risk_pending(monkeypatch, tmp_path):
    client = client_with_demo_db(monkeypatch, tmp_path)

    response = client.post(
        "/api/v1/demo/tasks",
        json={"scenario": "smart_home_safety", "user_input": "把客厅灯关掉"},
    )

    assert response.status_code == 200
    task = response.json()["task"]
    assert task["risk_level"] == "MEDIUM"
    assert task["confirmation_status"] == "PENDING"


def test_task_history_api_after_demo_persists(monkeypatch, tmp_path):
    client = client_with_demo_db(monkeypatch, tmp_path)
    client.post(
        "/api/v1/demo/tasks",
        json={"scenario": "vehicle_safety", "user_input": "解锁我的车"},
    )

    listed = client.get("/api/v1/tasks")
    task_id = listed.json()[0]["id"]
    detail = client.get(f"/api/v1/tasks/{task_id}")

    assert listed.status_code == 200
    assert detail.status_code == 200
    assert detail.json()["id"] == task_id


def test_trigger_api_for_frontend_demo(monkeypatch, tmp_path):
    client = client_with_demo_db(monkeypatch, tmp_path)
    db_path = tmp_path / "flowmate_stage27.db"
    repository = SQLiteTriggerRepository(db_path)
    trigger = CalendarTriggerRegistrationService(
        repository,
        lead_time_minutes=60,
    ).register_event(
        CalendarTriggerSourceEvent(
            id="frontend-trigger-event",
            summary="Morning Meeting",
            start=datetime.fromisoformat("2026-08-12T08:30:00+08:00"),
            location="人民广场",
        ),
        now=datetime.fromisoformat("2026-08-12T07:29:00+08:00"),
    )

    listed = client.get("/api/v1/triggers")
    tick = client.post("/api/v1/triggers/tick?now=2026-08-11T23:30:00Z")
    detail = client.get(f"/api/v1/triggers/{trigger.id}")

    assert listed.status_code == 200
    assert listed.json()[0]["id"] == trigger.id
    assert tick.status_code == 200
    assert tick.json()["generated_task_ids"]
    assert detail.json()["status"] == "FIRED"
