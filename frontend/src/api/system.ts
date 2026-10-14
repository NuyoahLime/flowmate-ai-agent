import { requestJson } from "./client";
import type { SystemStatus } from "../types";

export function getSystemStatus(): Promise<SystemStatus> {
  return requestJson<SystemStatus>("/api/v1/system/status");
}
