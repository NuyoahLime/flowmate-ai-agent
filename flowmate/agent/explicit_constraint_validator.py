import re
from dataclasses import dataclass
from datetime import date, timedelta

from flowmate.agent.planner import PlannerOutputValidationError
from flowmate.schemas import PlannedTask


@dataclass(frozen=True)
class ExplicitNavigationConstraints:
    date: str | None = None
    clock_time: str | None = None
    origin: str | None = None
    destination: str | None = None


class ExplicitConstraintValidator:
    _route_pattern = re.compile(
        r"从\s*(?P<origin>[^，。,.!?！？]+?)\s*(?:出发)?\s*"
        r"[，,]?\s*(?:去|到|前往)\s*(?P<destination>[^，。,.!?！？]+)"
    )
    _origin_only_pattern = re.compile(r"从\s*(?P<origin>[^，。,.!?！？]+?)\s*出发")
    _clock_pattern = re.compile(
        r"(?:(?P<period>凌晨|早上|上午|中午|下午|傍晚|晚上)\s*)?"
        r"(?P<hour>\d{1,2})\s*(?:[:：点时])\s*"
        r"(?P<minute>\d{1,2})?\s*分?"
    )
    _chinese_clock_pattern = re.compile(
        r"(?:(?P<period>凌晨|早上|上午|中午|下午|傍晚|晚上)\s*)?"
        r"(?P<hour>零|一|二|两|三|四|五|六|七|八|九|十|十一|十二)点"
        r"(?P<half>半)?"
    )
    _argument_clock_pattern = re.compile(r"(?<!\d)(?P<hour>\d{1,2}):(?P<minute>\d{2})(?!\d)")
    _tomorrow_markers = ("明天", "明早", "tomorrow")
    _location_alias_groups = (
        {"公司", "company", "office", "workplace", "unit"},
        {"家", "家里", "home"},
        {"学校", "school"},
    )
    _chinese_hours = {
        "零": 0,
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
        "十一": 11,
        "十二": 12,
    }

    def validate(self, user_input: str, planned_task: PlannedTask) -> None:
        constraints = self.extract(user_input)
        if not any(
            (
                constraints.date,
                constraints.clock_time,
                constraints.origin,
                constraints.destination,
            )
        ):
            return

        route_was_explicit = constraints.origin is not None and constraints.destination is not None
        navigation_steps = [
            step for step in planned_task.steps if step.tool_name == "navigation_tool"
        ]
        if route_was_explicit and not navigation_steps:
            raise PlannerOutputValidationError(
                "Explicit origin and destination require a navigation_tool step."
            )
        if constraints.origin is not None and constraints.destination is None and navigation_steps:
            raise PlannerOutputValidationError(
                "Navigation destination is missing from the user request; do not invent one."
            )
        if not navigation_steps:
            return

        arguments = navigation_steps[0].arguments
        self._validate_location("origin", constraints.origin, arguments.get("origin"))
        self._validate_location(
            "destination",
            constraints.destination,
            arguments.get("destination"),
        )
        self._validate_clock_time(constraints.clock_time, arguments.get("departure_time"))
        self._validate_date(constraints.date, arguments.get("departure_time"))

    def extract(self, user_input: str) -> ExplicitNavigationConstraints:
        route_match = self._route_pattern.search(user_input)
        origin_only_match = self._origin_only_pattern.search(user_input)
        clock_match = self._clock_pattern.search(user_input)
        chinese_clock_match = self._chinese_clock_pattern.search(user_input)
        date = "tomorrow" if any(marker in user_input for marker in self._tomorrow_markers) else None

        return ExplicitNavigationConstraints(
            date=date,
            clock_time=(
                self._normalize_clock(clock_match)
                if clock_match
                else self._normalize_chinese_clock(chinese_clock_match)
                if chinese_clock_match
                else None
            ),
            origin=(
                self._clean_location(route_match.group("origin"))
                if route_match
                else self._clean_location(origin_only_match.group("origin"))
                if origin_only_match
                else None
            ),
            destination=(
                self._clean_location(route_match.group("destination")) if route_match else None
            ),
        )

    def _normalize_clock(self, match: re.Match[str]) -> str:
        hour = int(match.group("hour"))
        minute = int(match.group("minute") or "0")
        period = match.group("period")
        if period in {"下午", "傍晚", "晚上"} and hour < 12:
            hour += 12
        elif period == "中午" and hour < 11:
            hour += 12
        elif period == "凌晨" and hour == 12:
            hour = 0
        return f"{hour:02d}:{minute:02d}"

    def _normalize_chinese_clock(self, match: re.Match[str]) -> str:
        hour = self._chinese_hours[match.group("hour")]
        minute = 30 if match.group("half") else 0
        period = match.group("period")
        if period in {"下午", "傍晚", "晚上"} and hour < 12:
            hour += 12
        elif period == "中午" and hour < 11:
            hour += 12
        elif period == "凌晨" and hour == 12:
            hour = 0
        return f"{hour:02d}:{minute:02d}"

    def _clean_location(self, value: str) -> str:
        return value.strip().rstrip("。！!?？")

    def _validate_location(self, field: str, expected: str | None, actual: object) -> None:
        if expected is None:
            return
        if not isinstance(actual, str) or not self._locations_match(expected, actual):
            raise PlannerOutputValidationError(
                f"Planner did not preserve explicit {field}: expected={expected!r}, actual={actual!r}."
            )

    def _locations_match(self, expected: str, actual: str) -> bool:
        expected_value = expected.strip().lower()
        actual_value = actual.strip().lower()
        if (
            expected_value == actual_value
            or expected_value in actual_value
            or actual_value in expected_value
        ):
            return True
        return any(
            expected_value in alias_group and actual_value in alias_group
            for alias_group in self._location_alias_groups
        )

    def _validate_clock_time(self, expected: str | None, actual: object) -> None:
        if expected is None:
            return
        actual_clock = None
        if isinstance(actual, str):
            match = self._argument_clock_pattern.search(actual)
            if match:
                actual_clock = f"{int(match.group('hour')):02d}:{match.group('minute')}"
        if actual_clock != expected:
            raise PlannerOutputValidationError(
                "Planner did not preserve explicit departure time: "
                f"expected={expected!r}, actual={actual!r}."
            )

    def _validate_date(self, expected: str | None, actual: object) -> None:
        if expected != "tomorrow":
            return
        if not isinstance(actual, str) or not any(
            marker in actual.lower()
            for marker in (
                "tomorrow",
                "明天",
                "明日",
                (date.today() + timedelta(days=1)).isoformat(),
            )
        ):
            raise PlannerOutputValidationError(
                "Planner did not preserve explicit departure date: "
                f"expected='tomorrow', actual={actual!r}."
            )
