import { requestJson } from "./client";
import type { DemoTaskResponse, Task } from "../types";

export function listTasks(): Promise<Task[]> {
  return requestJson<Task[]>("/api/v1/tasks");
}

export function getTask(taskId: string): Promise<Task> {
  return requestJson<Task>(`/api/v1/tasks/${taskId}`);
}

export function createDemoTask(
  scenario: string,
  userInput: string
): Promise<DemoTaskResponse> {
  return requestJson<DemoTaskResponse>("/api/v1/demo/tasks", {
    method: "POST",
    body: JSON.stringify({ scenario, user_input: userInput })
  });
}

export function createAgentTask(userInput: string): Promise<DemoTaskResponse> {
  return requestJson<DemoTaskResponse>("/api/v1/agent/tasks", {
    method: "POST",
    body: JSON.stringify({ user_input: userInput })
  });
}

export function confirmTask(taskId: string): Promise<Task> {
  return requestJson<Task>(`/api/v1/tasks/${taskId}/confirm`, {
    method: "POST"
  });
}

export function rejectTask(taskId: string): Promise<Task> {
  return requestJson<Task>(`/api/v1/tasks/${taskId}/reject`, {
    method: "POST"
  });
}
