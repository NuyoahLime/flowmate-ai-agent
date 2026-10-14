from dataclasses import dataclass


@dataclass(frozen=True)
class TemporalWindow:
    name: str
    date: str
    start_time: str | None
    end_time: str | None
    phrases: tuple[str, ...]


CALENDAR_TEMPORAL_WINDOWS = {
    "whole_day": TemporalWindow(
        name="whole_day",
        date="tomorrow",
        start_time=None,
        end_time=None,
        phrases=("tomorrow",),
    ),
    "morning": TemporalWindow(
        name="morning",
        date="tomorrow",
        start_time="06:00",
        end_time="12:00",
        phrases=("tomorrow morning", "明早", "明天上午"),
    ),
    "afternoon": TemporalWindow(
        name="afternoon",
        date="tomorrow",
        start_time="12:00",
        end_time="18:00",
        phrases=("tomorrow afternoon", "明天下午"),
    ),
    "evening": TemporalWindow(
        name="evening",
        date="tomorrow",
        start_time="18:00",
        end_time="23:59",
        phrases=("tomorrow evening", "明晚", "明天晚上"),
    ),
}


def build_calendar_temporal_conventions_prompt() -> str:
    lines = ["Calendar temporal conventions:"]
    for window in CALENDAR_TEMPORAL_WINDOWS.values():
        phrase_text = ", ".join(f'"{phrase}"' for phrase in window.phrases)
        lines.append(f"- {phrase_text}: date={window.date}")
        if window.start_time is None or window.end_time is None:
            lines.append("  omit start_time and end_time")
        else:
            lines.append(
                f"  start_time={window.start_time}, end_time={window.end_time}"
            )
    return "\n".join(lines)
