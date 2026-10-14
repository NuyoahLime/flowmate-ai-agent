export type TaskStatus =
  | "CREATED"
  | "PLANNED"
  | "WAITING_CONFIRMATION"
  | "EXECUTING"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED";

export type ToolCallStatus = "PENDING" | "RUNNING" | "SUCCESS" | "FAILED";
export type RiskLevel = "LOW" | "MEDIUM" | "HIGH";
export type ConfirmationStatus = "NOT_REQUIRED" | "PENDING" | "CONFIRMED" | "REJECTED";
export type TriggerStatus = "ACTIVE" | "FIRED" | "CANCELLED" | "EXPIRED";

export interface ToolCall {
  tool_name: string;
  arguments: Record<string, unknown>;
  status: ToolCallStatus;
  result: Record<string, unknown> | null;
  error: string | null;
}

export interface PlanStep {
  id: string;
  order: number;
  description: string;
  tool_name: string;
  tool_call: ToolCall | null;
  status: ToolCallStatus;
}

export interface Task {
  id: string;
  user_input: string;
  goal: string;
  status: TaskStatus;
  risk_level: RiskLevel;
  requires_confirmation: boolean;
  confirmation_status: ConfirmationStatus;
  steps: PlanStep[];
}

export interface Trigger {
  id: string;
  trigger_type: string;
  status: TriggerStatus;
  source_event_id: string;
  source_event_start: string;
  source_event_location: string;
  source_event_summary: string | null;
  lead_time_minutes: number;
  created_at: string;
  last_evaluated_at: string | null;
  fired_at: string | null;
  generated_task_id: string | null;
}

export interface DemoTaskResponse {
  scenario: string;
  task: Task | null;
  notification_task: Task | null;
  dynamic_state: DynamicState | null;
}

export interface DynamicState {
  phase: string;
  selected_event: Record<string, unknown> | null;
  observations: ToolObservation[];
  continuation_observations: ToolObservation[];
  side_effect_status: string | null;
  failure_type: string | null;
  error: string | null;
}

export interface ToolObservation {
  tool_name: string;
  step_id: string | null;
  result: Record<string, unknown>;
  error: string | null;
}

export interface SystemStatus {
  backend_ready: boolean;
  database_ready: boolean;
  demo_mode: boolean;
  tool_mode: "mock" | "real_information";
  providers: Record<string, string>;
  integrations: Record<string, { status: string }>;
}

export interface EvalBundle {
  planner_v3: EvalResult;
  proactive_trigger_v1: EvalResult;
}

export interface EvalResult {
  metrics: Record<string, number | string | null>;
  results?: unknown[];
}

export interface TriggerTickResult {
  evaluated_count: number;
  generated_task_ids: string[];
  expired_trigger_ids: string[];
}

export type DeviceType = "PHONE" | "CAR";
export type DeviceStatus = "ONLINE" | "OFFLINE";
export type DeviceCapability =
  | "CALENDAR"
  | "WEATHER"
  | "NAVIGATION"
  | "NAVIGATION_VIEW"
  | "NOTIFICATION"
  | "VEHICLE_STATUS";
export type HandoffStatus = "PENDING" | "ACCEPTED" | "REJECTED" | "CANCELLED";

export interface Device {
  id: string;
  user_id: string;
  device_type: DeviceType;
  display_name: string;
  status: DeviceStatus;
  last_seen_at: string | null;
  created_at: string;
  capabilities: DeviceCapability[];
}

export interface TaskDeviceState {
  task_id: string;
  owner_user_id: string;
  origin_device_id: string;
  current_device_id: string;
  version: number;
  updated_at: string;
}

export interface RoutingDecision {
  task_id: string;
  recommended_device: string;
  reason: string;
  capability: DeviceCapability;
  available: boolean;
}

export interface HandoffContext {
  goal: string;
  meeting_summary: string | null;
  meeting_start: string | null;
  destination: string | null;
  navigation_summary: string | null;
  risk_level: string;
  confirmation_status: string;
}

export interface Handoff {
  task_id: string;
  handoff_id: string;
  user_id: string;
  source_device: string;
  target_device: string;
  required_capability: DeviceCapability;
  status: HandoffStatus;
  task_version: number;
  context: HandoffContext;
  created_at: string;
  accepted_at: string | null;
  rejected_at: string | null;
  cancelled_at: string | null;
  state_transition_applied?: boolean;
  device_state?: TaskDeviceState;
}
