from fastapi import APIRouter, HTTPException

from flowmate.demo import DemoTaskRequest, DemoTaskResponse, DemoTaskService


router = APIRouter(prefix="/api/v1/demo", tags=["demo"])


@router.post("/tasks", response_model=DemoTaskResponse)
def create_demo_task(request: DemoTaskRequest):
    try:
        return DemoTaskService().create_demo_task(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
