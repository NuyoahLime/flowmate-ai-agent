from fastapi.testclient import TestClient

from flowmate.persistence import SQLiteTaskRepository
from flowmate.schemas import PlanStep, Task, TaskStatus, ToolCall


def test_list_task_history_api(monkeypatch, tmp_path):
    db_path = tmp_path / "flowmate_api_test.db"
    monkeypatch.setenv("FLOWMATE_DB_PATH", str(db_path))
    repository = SQLiteTaskRepository(db_path)
    repository.save_task(
        Task(
            id="task-api",
            user_input="明天上班帮我安排一下通勤",
            goal="安排通勤",
            status=TaskStatus.PLANNED,
            steps=[
                PlanStep(
                    id="step-weather",
                    order=1,
                    description="检查天气",
                    tool_name="weather_tool",
                    tool_call=ToolCall(
                        tool_name="weather_tool",
                        arguments={"location": "current_city", "date": "tomorrow"},
                    ),
                )
            ],
        )
    )

    from main import app

    response = TestClient(app).get("/api/v1/tasks")

    assert response.status_code == 200
    assert response.json()[0]["id"] == "task-api"


def test_get_task_history_api(monkeypatch, tmp_path):
    db_path = tmp_path / "flowmate_api_test.db"
    monkeypatch.setenv("FLOWMATE_DB_PATH", str(db_path))
    SQLiteTaskRepository(db_path).save_task(
        Task(
            id="task-detail",
            user_input="明天上班帮我安排一下通勤",
            goal="安排通勤",
            status=TaskStatus.PLANNED,
            steps=[],
        )
    )

    from main import app

    response = TestClient(app).get("/api/v1/tasks/task-detail")

    assert response.status_code == 200
    assert response.json()["id"] == "task-detail"


def test_get_missing_task_history_api_returns_404(monkeypatch, tmp_path):
    monkeypatch.setenv("FLOWMATE_DB_PATH", str(tmp_path / "flowmate_api_test.db"))

    from main import app

    response = TestClient(app).get("/api/v1/tasks/missing")

    assert response.status_code == 404
