import { requestJson } from "./client";
import type { EvalBundle } from "../types";

export function getEvals(): Promise<EvalBundle> {
  return requestJson<EvalBundle>("/api/v1/evals");
}
