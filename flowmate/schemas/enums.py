from enum import Enum


class TaskStatus(str, Enum):
    CREATED = "CREATED"
    PLANNED = "PLANNED"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ToolCallStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class ConfirmationStatus(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"


class DynamicPlanningPhase(str, Enum):
    INITIAL_PLANNING = "INITIAL_PLANNING"
    WAITING_OBSERVATION = "WAITING_OBSERVATION"
    CONTINUATION_PLANNING = "CONTINUATION_PLANNING"
    CONTINUATION_EXECUTING = "CONTINUATION_EXECUTING"
    SIDE_EFFECT_PLANNING = "SIDE_EFFECT_PLANNING"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    SIDE_EFFECT_EXECUTING = "SIDE_EFFECT_EXECUTING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class DynamicPlanningFailureType(str, Enum):
    NO_CALENDAR_EVENT = "no_calendar_event"
    MISSING_EVENT_LOCATION = "missing_event_location"
    TOOL_EXECUTION_ERROR = "tool_execution_error"
    CONTINUATION_PLANNING_ERROR = "continuation_planning_error"
    MAX_ITERATIONS_EXCEEDED = "max_iterations_exceeded"
    UNSUPPORTED_DYNAMIC_GOAL = "unsupported_dynamic_goal"
    OBSERVATION_GROUNDING_ERROR = "observation_grounding_error"
    CONTINUATION_EXECUTION_ERROR = "continuation_execution_error"
    SIDE_EFFECT_PROPOSAL_ERROR = "side_effect_proposal_error"
    SIDE_EFFECT_RISK_POLICY_ERROR = "side_effect_risk_policy_error"
    SIDE_EFFECT_EXECUTION_ERROR = "side_effect_execution_error"
    NOTIFICATION_GROUNDING_ERROR = "notification_grounding_error"
    UNSUPPORTED_SCHEDULED_NOTIFICATION = "unsupported_scheduled_notification"
    UNSUPPORTED_CONDITIONAL_NOTIFICATION = "unsupported_conditional_notification"


class TriggerType(str, Enum):
    CALENDAR_EVENT_LEAD_TIME = "CALENDAR_EVENT_LEAD_TIME"


class TriggerStatus(str, Enum):
    ACTIVE = "ACTIVE"
    FIRED = "FIRED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
