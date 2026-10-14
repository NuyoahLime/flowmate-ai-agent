from typing import Protocol, runtime_checkable

from flowmate.schemas import Task


class UnsupportedPlanningScenarioError(Exception):
    pass


class PlannerOutputValidationError(Exception):
    pass


@runtime_checkable
class Planner(Protocol):
    def plan(self, user_input: str) -> Task:
        ...
