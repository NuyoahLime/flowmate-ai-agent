import sqlite3
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from flowmate.agent import RiskPolicy, TaskConfirmationService
from flowmate.cross_device import (
    CrossDeviceAuthorizationError,
    CrossDeviceConflictError,
    CrossDeviceValidationError,
    DeviceCapability,
    DeviceRegistryService,
    DeviceRouter,
    DeviceStatus,
    DeviceType,
    HandoffService,
    HandoffStatus,
    SQLiteCrossDeviceRepository,
    TaskDeviceStateService,
    seed_demo_devices,
)
from flowmate.cross_device.demo import (
    build_cross_device_commute_task,
    run_cross_device_smoke,
)
from flowmate.eval.cross_device_evaluator import CrossDeviceEvaluator
from flowmate.persistence import SCHEMA_VERSION, TaskPersistenceService
from flowmate.schemas import PlanStep, RiskLevel, Task, TaskStatus, ToolCall


NOW = datetime(2026, 9, 30, 8, 0, tzinfo=UTC)


@pytest.fixture
def prepared(tmp_path):
    db_path = tmp_path / "stage29.db"
    repository = SQLiteCrossDeviceRepository(db_path)
    seed_demo_devices(repository, now=NOW)
    registry = DeviceRegistryService(repository)
    registry.update_presence("phone_001", now=NOW)
    registry.update_presence("car_001", now=NOW)
    task = build_cross_device_commute_task()
    TaskPersistenceService(db_path=db_path).persist(task)
    states = TaskDeviceStateService(repository, db_path=db_path)
    state = states.initialize(
        task_id=task.id,
        owner_user_id="demo_user",
        origin_device_id="phone_001",
        now=NOW,
    )
    return db_path, repository, registry, task, states, state


def create_pending_handoff(prepared):
    db_path, repository, _, task, states, state = prepared
    service = HandoffService(repository, db_path=db_path)
    handoff = service.create_handoff(
        task_id=task.id,
        user_id="demo_user",
        source_device_id="phone_001",
        target_device_id="car_001",
        required_capability=DeviceCapability.NAVIGATION,
        expected_version=state.version,
        now=NOW + timedelta(seconds=1),
    )
    return service, handoff, states.get(task.id)


def test_schema_version_is_three(tmp_path):
    repository = SQLiteCrossDeviceRepository(tmp_path / "schema.db")
    with sqlite3.connect(repository.db_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION == 3


def test_v2_migration_preserves_existing_task(prepared):
    db_path, _, _, task, _, _ = prepared
    with sqlite3.connect(db_path) as connection:
        connection.execute("DROP TABLE handoffs")
        connection.execute("DROP TABLE task_device_state")
        connection.execute("DROP TABLE device_capabilities")
        connection.execute("DROP TABLE devices")
        connection.execute("DROP TABLE users")
        connection.execute("PRAGMA user_version = 2")
    SQLiteCrossDeviceRepository(db_path)
    assert TaskPersistenceService(db_path=db_path).load(task.id) is not None


def test_device_type_only_supports_phone_and_car():
    assert {item.value for item in DeviceType} == {"PHONE", "CAR"}


def test_demo_seed_creates_demo_user(prepared):
    _, repository, _, _, _, _ = prepared
    assert repository.get_user("demo_user").display_name == "FlowMate Demo User"


def test_demo_seed_registers_two_devices(prepared):
    _, _, registry, _, _, _ = prepared
    assert [item.id for item in registry.list_user_devices("demo_user", now=NOW)] == [
        "car_001",
        "phone_001",
    ]


def test_phone_capabilities_are_presentation_capabilities(prepared):
    _, _, registry, _, _, _ = prepared
    phone = registry.get_device("phone_001", now=NOW)
    assert DeviceCapability.NAVIGATION_VIEW in phone.capabilities
    assert DeviceCapability.NAVIGATION not in phone.capabilities


def test_car_has_navigation_and_mock_vehicle_status(prepared):
    _, _, registry, _, _, _ = prepared
    car = registry.get_device("car_001", now=NOW)
    assert car.capabilities == [DeviceCapability.NAVIGATION, DeviceCapability.VEHICLE_STATUS]


def test_existing_device_cannot_be_reassigned(prepared):
    _, repository, registry, _, _, _ = prepared
    registry.register_user("demo_user_2", "Other User", now=NOW)
    with pytest.raises(CrossDeviceAuthorizationError):
        registry.register_device(
            device_id="car_001",
            user_id="demo_user_2",
            device_type=DeviceType.CAR,
            display_name="Stolen Car",
            capabilities=[DeviceCapability.NAVIGATION],
            now=NOW,
        )


def test_heartbeat_marks_device_online(prepared):
    _, _, registry, _, _, _ = prepared
    assert registry.update_presence("car_001", now=NOW).status == DeviceStatus.ONLINE


def test_presence_expires_after_ten_seconds(prepared):
    _, _, registry, _, _, _ = prepared
    assert registry.get_device("car_001", now=NOW + timedelta(seconds=11)).status == DeviceStatus.OFFLINE


def test_mark_offline_is_immediate(prepared):
    _, _, registry, _, _, _ = prepared
    registry.mark_offline("car_001")
    assert registry.get_device("car_001", now=NOW).status == DeviceStatus.OFFLINE


def test_task_device_state_starts_on_phone(prepared):
    *_, state = prepared
    assert state.origin_device_id == state.current_device_id == "phone_001"
    assert state.version == 1


def test_task_device_state_initialization_is_idempotent(prepared):
    _, _, _, task, states, state = prepared
    again = states.initialize(
        task_id=task.id,
        owner_user_id="demo_user",
        origin_device_id="phone_001",
        now=NOW,
    )
    assert again == state


def test_task_device_state_rejects_wrong_owner(prepared):
    db_path, repository, registry, task, _, _ = prepared
    registry.register_user("demo_user_2", "Other User", now=NOW)
    registry.register_device(
        device_id="phone_002",
        user_id="demo_user_2",
        device_type=DeviceType.PHONE,
        display_name="Other Phone",
        capabilities=[DeviceCapability.NAVIGATION_VIEW],
        now=NOW,
    )
    with pytest.raises(CrossDeviceConflictError):
        TaskDeviceStateService(repository, db_path=db_path).initialize(
            task_id=task.id,
            owner_user_id="demo_user_2",
            origin_device_id="phone_002",
            now=NOW,
        )


def test_router_recommends_online_navigation_car(prepared):
    db_path, repository, _, task, _, _ = prepared
    decision = DeviceRouter(repository, db_path=db_path).recommend(task.id, now=NOW)
    assert decision.recommended_device == "car_001"
    assert decision.available is True
    assert "NAVIGATION" in decision.reason


def test_router_is_deterministic(prepared):
    db_path, repository, _, task, _, _ = prepared
    router = DeviceRouter(repository, db_path=db_path)
    assert router.recommend(task.id, now=NOW) == router.recommend(task.id, now=NOW)


def test_router_stays_when_navigation_context_missing(prepared):
    db_path, repository, _, _, states, _ = prepared
    task = Task(
        id="no-navigation",
        user_input="查看日程",
        goal="Calendar only",
        status=TaskStatus.COMPLETED,
        steps=[
            PlanStep(
                id="calendar-only",
                order=1,
                description="Read calendar",
                tool_name="calendar_tool",
                tool_call=ToolCall(tool_name="calendar_tool", arguments={"date": "tomorrow"}),
            )
        ],
    )
    TaskPersistenceService(db_path=db_path).persist(task)
    states.initialize(
        task_id=task.id,
        owner_user_id="demo_user",
        origin_device_id="phone_001",
        now=NOW,
    )
    decision = DeviceRouter(repository, db_path=db_path).recommend(task.id, now=NOW)
    assert decision.recommended_device == "phone_001"
    assert decision.available is False


def test_router_does_not_recommend_offline_car(prepared):
    db_path, repository, registry, task, _, _ = prepared
    registry.mark_offline("car_001")
    decision = DeviceRouter(repository, db_path=db_path).recommend(task.id, now=NOW)
    assert decision.recommended_device == "phone_001"
    assert decision.available is False


def test_router_requires_navigation_capability(prepared):
    db_path, repository, _, task, _, _ = prepared
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE device_capabilities SET enabled = 0 WHERE device_id = ? AND capability = ?",
            ("car_001", DeviceCapability.NAVIGATION.value),
        )
    decision = DeviceRouter(repository, db_path=db_path).recommend(task.id, now=NOW)
    assert decision.recommended_device == "phone_001"


def test_create_handoff_is_pending(prepared):
    _, handoff, _ = create_pending_handoff(prepared)
    assert handoff.status == HandoffStatus.PENDING
    assert handoff.source_device_id == "phone_001"
    assert handoff.target_device_id == "car_001"


def test_pending_handoff_keeps_task_on_phone(prepared):
    _, _, state = create_pending_handoff(prepared)
    assert state.current_device_id == "phone_001"
    assert state.version == 2


def test_handoff_context_is_minimized_and_grounded(prepared):
    _, handoff, _ = create_pending_handoff(prepared)
    assert set(handoff.context.model_dump()) == {
        "goal",
        "meeting_summary",
        "meeting_start",
        "destination",
        "navigation_summary",
        "risk_level",
        "confirmation_status",
    }
    assert handoff.context.destination == "上海市人民广场"


def test_duplicate_pending_handoff_is_prevented(prepared):
    service, _, state = create_pending_handoff(prepared)
    with pytest.raises(CrossDeviceConflictError):
        service.create_handoff(
            task_id="cross-device-demo-task",
            user_id="demo_user",
            source_device_id="phone_001",
            target_device_id="car_001",
            required_capability=DeviceCapability.NAVIGATION,
            expected_version=state.version,
            now=NOW + timedelta(seconds=2),
        )


def test_wrong_user_device_cannot_receive_handoff(prepared):
    db_path, repository, registry, task, _, state = prepared
    registry.register_user("demo_user_2", "Other User", now=NOW)
    registry.register_device(
        device_id="car_002",
        user_id="demo_user_2",
        device_type=DeviceType.CAR,
        display_name="Other Car",
        capabilities=[DeviceCapability.NAVIGATION],
        now=NOW,
    )
    registry.update_presence("car_002", now=NOW)
    with pytest.raises(CrossDeviceAuthorizationError):
        HandoffService(repository, db_path=db_path).create_handoff(
            task_id=task.id,
            user_id="demo_user",
            source_device_id="phone_001",
            target_device_id="car_002",
            required_capability=DeviceCapability.NAVIGATION,
            expected_version=state.version,
            now=NOW,
        )


def test_offline_target_cannot_receive_handoff(prepared):
    db_path, repository, registry, task, _, state = prepared
    registry.mark_offline("car_001")
    with pytest.raises(CrossDeviceConflictError, match="offline"):
        HandoffService(repository, db_path=db_path).create_handoff(
            task_id=task.id,
            user_id="demo_user",
            source_device_id="phone_001",
            target_device_id="car_001",
            required_capability=DeviceCapability.NAVIGATION,
            expected_version=state.version,
            now=NOW,
        )


def test_target_missing_capability_cannot_receive_handoff(prepared):
    db_path, repository, registry, task, _, state = prepared
    registry.register_device(
        device_id="car_003",
        user_id="demo_user",
        device_type=DeviceType.CAR,
        display_name="Status-only Car",
        capabilities=[DeviceCapability.VEHICLE_STATUS],
        now=NOW,
    )
    registry.update_presence("car_003", now=NOW)
    with pytest.raises(CrossDeviceValidationError, match="lacks NAVIGATION"):
        HandoffService(repository, db_path=db_path).create_handoff(
            task_id=task.id,
            user_id="demo_user",
            source_device_id="phone_001",
            target_device_id="car_003",
            required_capability=DeviceCapability.NAVIGATION,
            expected_version=state.version,
            now=NOW,
        )


def test_create_handoff_rejects_stale_version(prepared):
    db_path, repository, _, task, _, _ = prepared
    with pytest.raises(CrossDeviceConflictError, match="version conflict"):
        HandoffService(repository, db_path=db_path).create_handoff(
            task_id=task.id,
            user_id="demo_user",
            source_device_id="phone_001",
            target_device_id="car_001",
            required_capability=DeviceCapability.NAVIGATION,
            expected_version=99,
            now=NOW,
        )


def test_accept_handoff_changes_current_device_atomically(prepared):
    service, handoff, state = create_pending_handoff(prepared)
    accepted, final_state, changed = service.accept_handoff(
        handoff.id,
        target_device_id="car_001",
        expected_version=state.version,
        now=NOW + timedelta(seconds=2),
    )
    assert accepted.status == HandoffStatus.ACCEPTED
    assert final_state.current_device_id == "car_001"
    assert final_state.version == 3
    assert changed is True


def test_duplicate_accept_is_idempotent_without_version_increment(prepared):
    service, handoff, state = create_pending_handoff(prepared)
    _, first_state, first_changed = service.accept_handoff(
        handoff.id,
        target_device_id="car_001",
        expected_version=state.version,
        now=NOW + timedelta(seconds=2),
    )
    _, second_state, second_changed = service.accept_handoff(
        handoff.id,
        target_device_id="car_001",
        expected_version=state.version,
        now=NOW + timedelta(seconds=3),
    )
    assert first_changed is True
    assert second_changed is False
    assert second_state.version == first_state.version


def test_accept_rejects_wrong_target_device(prepared):
    service, handoff, state = create_pending_handoff(prepared)
    with pytest.raises(CrossDeviceAuthorizationError):
        service.accept_handoff(
            handoff.id,
            target_device_id="phone_001",
            expected_version=state.version,
            now=NOW + timedelta(seconds=2),
        )


def test_reject_keeps_current_device_on_phone(prepared):
    service, handoff, state = create_pending_handoff(prepared)
    rejected, final_state = service.reject_handoff(
        handoff.id,
        target_device_id="car_001",
        expected_version=state.version,
        now=NOW + timedelta(seconds=2),
    )
    assert rejected.status == HandoffStatus.REJECTED
    assert final_state.current_device_id == "phone_001"
    assert final_state.version == 3


def test_cancel_requires_source_device(prepared):
    service, handoff, state = create_pending_handoff(prepared)
    with pytest.raises(CrossDeviceAuthorizationError):
        service.cancel_handoff(
            handoff.id,
            source_device_id="car_001",
            expected_version=state.version,
            now=NOW + timedelta(seconds=2),
        )


def test_restart_preserves_accepted_handoff_and_device_owner(prepared):
    db_path, *_ = prepared
    service, handoff, state = create_pending_handoff(prepared)
    service.accept_handoff(
        handoff.id,
        target_device_id="car_001",
        expected_version=state.version,
        now=NOW + timedelta(seconds=2),
    )
    reopened = SQLiteCrossDeviceRepository(db_path)
    assert reopened.get_handoff(handoff.id).status == HandoffStatus.ACCEPTED
    assert reopened.get_task_device_state(handoff.task_id).current_device_id == "car_001"


def test_phone_poll_reads_car_accept_version(prepared):
    db_path, *_ = prepared
    service, handoff, state = create_pending_handoff(prepared)
    service.accept_handoff(
        handoff.id,
        target_device_id="car_001",
        expected_version=state.version,
        now=NOW + timedelta(seconds=2),
    )
    phone_poll = TaskDeviceStateService(db_path=db_path).get(handoff.task_id)
    assert phone_poll.version == state.version + 1
    assert phone_poll.current_device_id == "car_001"


def test_confirmation_consistency_allows_only_one_transition(prepared):
    db_path, repository, _, _, states, _ = prepared
    task = Task(
        id="confirm-once",
        user_input="解锁我的车",
        goal="Unlock mock vehicle",
        status=TaskStatus.PLANNED,
        risk_level=RiskLevel.LOW,
        steps=[
            PlanStep(
                id="vehicle-unlock",
                order=1,
                description="Unlock mock vehicle.",
                tool_name="vehicle_tool",
                tool_call=ToolCall(
                    tool_name="vehicle_tool",
                    arguments={"vehicle_id": "my-car", "action": "unlock"},
                ),
            )
        ],
    )
    RiskPolicy().apply_to_task(task)
    TaskConfirmationService().request_confirmation(task)
    persistence = TaskPersistenceService(db_path=db_path)
    persistence.persist(task)
    state = states.initialize(
        task_id=task.id,
        owner_user_id="demo_user",
        origin_device_id="phone_001",
        now=NOW,
    )
    states.claim_confirmation(
        task_id=task.id,
        device_id="phone_001",
        expected_version=state.version,
        confirmed=True,
        now=NOW + timedelta(seconds=1),
    )
    with pytest.raises(CrossDeviceConflictError):
        states.claim_confirmation(
            task_id=task.id,
            device_id="car_001",
            expected_version=state.version,
            confirmed=True,
            now=NOW + timedelta(seconds=1),
        )
    assert persistence.load(task.id).confirmation_status.value == "CONFIRMED"


def test_wrong_user_device_cannot_confirm(prepared):
    db_path, repository, registry, _, states, _ = prepared
    registry.register_user("demo_user_2", "Other User", now=NOW)
    registry.register_device(
        device_id="phone_002",
        user_id="demo_user_2",
        device_type=DeviceType.PHONE,
        display_name="Other Phone",
        capabilities=[DeviceCapability.NOTIFICATION],
        now=NOW,
    )
    task = Task(
        id="confirm-isolated",
        user_input="提醒我",
        goal="Notification",
        status=TaskStatus.PLANNED,
        risk_level=RiskLevel.LOW,
        steps=[
            PlanStep(
                id="notify",
                order=1,
                description="Notify",
                tool_name="notification_tool",
                tool_call=ToolCall(
                    tool_name="notification_tool",
                    arguments={"title": "Done", "message": "Done", "channel": "mobile"},
                ),
            )
        ],
    )
    RiskPolicy().apply_to_task(task)
    TaskConfirmationService().request_confirmation(task)
    TaskPersistenceService(db_path=db_path).persist(task)
    state = states.initialize(
        task_id=task.id,
        owner_user_id="demo_user",
        origin_device_id="phone_001",
        now=NOW,
    )
    with pytest.raises(CrossDeviceAuthorizationError):
        states.claim_confirmation(
            task_id=task.id,
            device_id="phone_002",
            expected_version=state.version,
            confirmed=True,
            now=NOW,
        )


def test_offline_smoke_proves_same_task_and_no_real_calls(tmp_path):
    result = run_cross_device_smoke(tmp_path / "smoke.db")
    assert result["same_task_id"] is True
    assert result["context_reused"] is True
    assert result["final_current_device"] == "car_001"
    assert result["phone_post_handoff_current_device"] == "car_001"
    assert all(
        result[name] == 0
        for name in (
            "real_vehicle_calls",
            "real_smart_home_calls",
            "real_feishu_calls",
            "real_google_calls",
            "real_weather_calls",
            "real_amap_calls",
        )
    )


def test_cross_device_api_end_to_end(monkeypatch, tmp_path):
    db_path = tmp_path / "api.db"
    monkeypatch.setenv("FLOWMATE_DB_PATH", str(db_path))
    monkeypatch.setenv("FLOWMATE_DEMO_MODE", "true")
    from main import app

    client = TestClient(app)
    assert client.post("/api/v1/cross-device/demo-seed").status_code == 200
    client.post("/api/v1/devices/phone_001/heartbeat")
    client.post("/api/v1/devices/car_001/heartbeat")
    task = build_cross_device_commute_task("api-cross-device-task")
    TaskPersistenceService(db_path=db_path).persist(task)
    initialized = client.post(
        f"/api/v1/tasks/{task.id}/device-state",
        json={"owner_user_id": "demo_user", "origin_device_id": "phone_001"},
    )
    assert initialized.status_code == 200
    route = client.get(f"/api/v1/tasks/{task.id}/device-route")
    assert route.json()["recommended_device"] == "car_001"
    pending = client.post(
        f"/api/v1/tasks/{task.id}/handoffs",
        json={
            "user_id": "demo_user",
            "source_device_id": "phone_001",
            "target_device_id": "car_001",
            "expected_version": initialized.json()["version"],
            "required_capability": "NAVIGATION",
        },
    )
    assert pending.status_code == 200
    accepted = client.post(
        f"/api/v1/handoffs/{pending.json()['handoff_id']}/accept",
        json={"device_id": "car_001", "expected_version": pending.json()["task_version"]},
    )
    assert accepted.status_code == 200
    assert accepted.json()["device_state"]["current_device_id"] == "car_001"


def test_cross_device_api_returns_409_for_stale_version(monkeypatch, tmp_path):
    db_path = tmp_path / "api-conflict.db"
    monkeypatch.setenv("FLOWMATE_DB_PATH", str(db_path))
    from main import app

    client = TestClient(app)
    client.post("/api/v1/cross-device/demo-seed")
    client.post("/api/v1/devices/phone_001/heartbeat")
    client.post("/api/v1/devices/car_001/heartbeat")
    task = build_cross_device_commute_task("api-conflict-task")
    TaskPersistenceService(db_path=db_path).persist(task)
    client.post(
        f"/api/v1/tasks/{task.id}/device-state",
        json={"owner_user_id": "demo_user", "origin_device_id": "phone_001"},
    )
    response = client.post(
        f"/api/v1/tasks/{task.id}/handoffs",
        json={
            "user_id": "demo_user",
            "source_device_id": "phone_001",
            "target_device_id": "car_001",
            "expected_version": 99,
            "required_capability": "NAVIGATION",
        },
    )
    assert response.status_code == 409


def test_cross_device_eval_has_sixteen_cases():
    result = CrossDeviceEvaluator().evaluate("evals/cross_device_eval_v1.json")
    assert result["metrics"]["cases"] == 16


def test_cross_device_eval_metrics_are_all_one():
    result = CrossDeviceEvaluator().evaluate("evals/cross_device_eval_v1.json")
    assert all(
        value == 1.0
        for key, value in result["metrics"].items()
        if key != "cases"
    )


def test_coordinated_confirmation_api_rejects_second_client(monkeypatch, tmp_path):
    db_path = tmp_path / "api-confirm.db"
    monkeypatch.setenv("FLOWMATE_DB_PATH", str(db_path))
    monkeypatch.setenv("FLOWMATE_DEMO_MODE", "true")
    from main import app

    client = TestClient(app)
    client.post("/api/v1/cross-device/demo-seed")
    client.post("/api/v1/devices/phone_001/heartbeat")
    client.post("/api/v1/devices/car_001/heartbeat")
    created = client.post(
        "/api/v1/demo/tasks",
        json={"scenario": "vehicle_safety", "user_input": "解锁我的车"},
    )
    task_id = created.json()["task"]["id"]
    state = client.post(
        f"/api/v1/tasks/{task_id}/device-state",
        json={"owner_user_id": "demo_user", "origin_device_id": "phone_001"},
    ).json()
    first = client.post(
        f"/api/v1/tasks/{task_id}/confirm",
        json={"device_id": "phone_001", "expected_version": state["version"]},
    )
    second = client.post(
        f"/api/v1/tasks/{task_id}/confirm",
        json={"device_id": "car_001", "expected_version": state["version"]},
    )
    assert first.status_code == 200
    assert first.json()["status"] == "COMPLETED"
    assert first.json()["steps"][0]["tool_call"]["result"]["status"] == "mock_executed"
    assert second.status_code == 409
