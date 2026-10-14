import json
from enum import Enum
from pathlib import Path

from pydantic import BaseModel


class PlannerEvalChangeType(str, Enum):
    UNCHANGED = "unchanged"
    CAPABILITY_DRIVEN_RELABEL = "capability_driven_relabel"
    CAPABILITY_DRIVEN_PARAMETER_UPDATE = "capability_driven_parameter_update"


class PlannerEvalAuditRecord(BaseModel):
    case_id: str
    v2_category: str
    v2_supported: bool
    v2_expected_tools: list[str]
    v3_supported: bool
    v3_expected_tools: list[str]
    v3_included: bool
    v3_case_id: str | None
    change_type: PlannerEvalChangeType
    change_reason: str
    source_stage: str


def load_planner_eval_audit(path: str | Path) -> list[PlannerEvalAuditRecord]:
    with Path(path).open("r", encoding="utf-8") as file:
        raw_records = json.load(file)
    return [PlannerEvalAuditRecord.model_validate(record) for record in raw_records]
