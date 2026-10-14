import { requestJson } from "./client";
import type {
  Device,
  Handoff,
  HandoffStatus,
  RoutingDecision,
  TaskDeviceState
} from "../types";

export function seedCrossDeviceDemo(): Promise<unknown> {
  return requestJson("/api/v1/cross-device/demo-seed", { method: "POST" });
}

export function heartbeatDevice(deviceId: string): Promise<Device> {
  return requestJson<Device>(`/api/v1/devices/${deviceId}/heartbeat`, {
    method: "POST"
  });
}

export function getDevice(deviceId: string): Promise<Device> {
  return requestJson<Device>(`/api/v1/devices/${deviceId}`);
}

export function listUserDevices(userId: string): Promise<Device[]> {
  return requestJson<Device[]>(`/api/v1/users/${userId}/devices`);
}

export function initializeTaskDeviceState(
  taskId: string,
  ownerUserId: string,
  originDeviceId: string
): Promise<TaskDeviceState> {
  return requestJson<TaskDeviceState>(`/api/v1/tasks/${taskId}/device-state`, {
    method: "POST",
    body: JSON.stringify({
      owner_user_id: ownerUserId,
      origin_device_id: originDeviceId
    })
  });
}

export function getTaskDeviceState(taskId: string): Promise<TaskDeviceState> {
  return requestJson<TaskDeviceState>(`/api/v1/tasks/${taskId}/device-state`);
}

export function getDeviceRoute(taskId: string): Promise<RoutingDecision> {
  return requestJson<RoutingDecision>(`/api/v1/tasks/${taskId}/device-route`);
}

export function createHandoff(
  taskId: string,
  expectedVersion: number
): Promise<Handoff> {
  return requestJson<Handoff>(`/api/v1/tasks/${taskId}/handoffs`, {
    method: "POST",
    body: JSON.stringify({
      user_id: "demo_user",
      source_device_id: "phone_001",
      target_device_id: "car_001",
      expected_version: expectedVersion,
      required_capability: "NAVIGATION"
    })
  });
}

export function listTaskHandoffs(taskId: string): Promise<Handoff[]> {
  return requestJson<Handoff[]>(`/api/v1/tasks/${taskId}/handoffs`);
}

export function listIncomingHandoffs(
  deviceId: string,
  status?: HandoffStatus
): Promise<Handoff[]> {
  const query = status ? `?status=${status}` : "";
  return requestJson<Handoff[]>(`/api/v1/devices/${deviceId}/handoffs${query}`);
}

export function acceptHandoff(
  handoffId: string,
  deviceId: string,
  expectedVersion: number
): Promise<Handoff> {
  return requestJson<Handoff>(`/api/v1/handoffs/${handoffId}/accept`, {
    method: "POST",
    body: JSON.stringify({ device_id: deviceId, expected_version: expectedVersion })
  });
}

export function rejectHandoff(
  handoffId: string,
  deviceId: string,
  expectedVersion: number
): Promise<Handoff> {
  return requestJson<Handoff>(`/api/v1/handoffs/${handoffId}/reject`, {
    method: "POST",
    body: JSON.stringify({ device_id: deviceId, expected_version: expectedVersion })
  });
}
