import json
from pathlib import Path

from fastapi import APIRouter


router = APIRouter(prefix="/api/v1/evals", tags=["evals"])

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@router.get("")
def get_evals():
    return {
        "planner_v3": _load_result("llm_planner_v3_stage20.json"),
        "proactive_trigger_v1": _load_result("proactive_trigger_eval_v1.json"),
    }


@router.get("/planner-v3")
def get_planner_v3_eval():
    return _load_result("llm_planner_v3_stage20.json")


@router.get("/proactive-trigger-v1")
def get_proactive_trigger_eval():
    return _load_result("proactive_trigger_eval_v1.json")


def _load_result(name: str):
    path = PROJECT_ROOT / "evals" / "results" / name
    if not path.exists():
        return {"available": False, "metrics": None, "results": []}
    return json.loads(path.read_text(encoding="utf-8"))
