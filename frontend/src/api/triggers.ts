import { requestJson } from "./client";
import type { Trigger, TriggerTickResult } from "../types";

export function listTriggers(): Promise<Trigger[]> {
  return requestJson<Trigger[]>("/api/v1/triggers");
}

export function getTrigger(triggerId: string): Promise<Trigger> {
  return requestJson<Trigger>(`/api/v1/triggers/${triggerId}`);
}

export function tickTriggers(): Promise<TriggerTickResult> {
  return requestJson<TriggerTickResult>("/api/v1/triggers/tick", {
    method: "POST"
  });
}
