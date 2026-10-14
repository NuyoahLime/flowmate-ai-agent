# Project Challenges

## 1. Rule Planner main set 100% but Challenge Set leakage

Problem: RuleBasedPlanner matched the main dataset perfectly.  
Why it matters: A perfect score can hide overfit rules.  
Initial approach: Keyword matching for morning commute.  
Exposed issue: Hard negatives could contain commute keywords but not require planning.  
How located: Challenge set with paraphrases and hard negatives.  
Final approach: Preserve baseline result and document boundary instead of pretending rules generalize.  
Trade-off: Rule baseline stays simple; LLMPlanner carries broader language coverage.  
Validation: Challenge results expose rule limitations.  
Interview line: A baseline is useful only if you also design cases that can break it.

## 2. Tool over-selection

Problem: LLMPlanner sometimes selected extra tools.  
Why it matters: Extra tools increase latency, cost and safety surface.  
Initial approach: Prompt-level tool list.  
Exposed issue: The model could still add unnecessary tools.  
How located: Minimality eval and extra tool rate.  
Final approach: Tight prompt wording plus program-side whitelist and eval tracking.  
Trade-off: Stricter planning can increase over-refusal risk.  
Validation: Planner Eval V3 Extra Tool Rate is 0.000.  
Interview line: Correct answer is not enough if the agent used unnecessary capability.

## 3. Capability Boundary

Problem: Unsupported requests must not be mapped to available tools.  
Why it matters: Wrong capability acceptance can create unsafe execution plans.  
Initial approach: Tool whitelist.  
Exposed issue: Whitelist alone does not express action-level capability.  
How located: Boundary eval for calendar write, unsupported vehicle and smart-home cases.  
Final approach: Capability authorization before Task construction.  
Trade-off: More explicit rules to maintain.  
Validation: Unsupported recall tracked in Planner Eval V3.  
Interview line: Unsupported is a valid product outcome, not a failure to answer.

## 4. Retry is not Re-plan

Problem: Provider instability and planning errors can look similar.  
Why it matters: Retrying a bad plan does not fix reasoning.  
Initial approach: Direct provider call.  
Exposed issue: Transient provider failures polluted planner evaluation.  
How located: Failure attribution work.  
Final approach: Bounded provider retry for provider errors only, with explicit attribution.  
Trade-off: More metrics, but clearer failures.  
Validation: Retry cases and recovery rate are recorded separately.  
Interview line: Retry handles transport uncertainty; re-plan handles task state change.

## 5. Observation-driven Dynamic Planning

Problem: Initial user input often lacks the full route destination.  
Why it matters: The agent must learn from tools, not guess.  
Initial approach: Static two-step commute plan.  
Exposed issue: Calendar location should drive later tools.  
How located: Morning commute dynamic scenario.  
Final approach: Calendar observation feeds continuation planning for weather and route.  
Trade-off: More runtime state to render and persist.  
Validation: Frontend timeline shows observation and re-plan.  
Interview line: The important jump is from function calling to observe-and-continue.

## 6. Vehicle action-aware risk

Problem: Vehicle status read and unlock action should not share risk.  
Why it matters: Tool name alone is too coarse for safety.  
Initial approach: Tool-level risk.  
Exposed issue: Vehicle actions have different impact levels.  
How located: Vehicle planner and authorization evals.  
Final approach: Action-aware RiskPolicy.  
Trade-off: Risk policy needs action semantics.  
Validation: HIGH-risk vehicle unlock remains pending until confirmation.  
Interview line: Risk belongs to intent plus action, not just tool category.

## 7. Real-world POI Grounding

Problem: Amap could return a valid route to the wrong People's Square.  
Why it matters: HTTP 200 and schema valid can still be semantically wrong.  
Initial approach: Use provider geocode result.  
Exposed issue: Wrong province/city produced a long-distance route.  
How located: Route distance and resolved location audit.  
Final approach: Origin context, POI region constraint, city limit and defensive validation.  
Trade-off: More conservative resolution.  
Validation: Resolved to Shanghai People's Square in the verified scenario.  
Interview line: Grounding quality is a product metric, not just an API integration detail.

## 8. Side-effect HITL

Problem: Notification and device actions must not happen silently.  
Why it matters: Agent side effects need user control.  
Initial approach: Task requires confirmation flag.  
Exposed issue: Confirmation state needs an invariant separate from policy need.  
How located: HITL state-flow tests.  
Final approach: ConfirmationStatus plus TaskConfirmationService.  
Trade-off: Extra state machine, clearer audit.  
Validation: Confirm executes once; reject executes zero times.  
Interview line: HITL is a backend safety gate, not a button decoration.

## 9. Persistence / transaction

Problem: Demo refresh should not lose Task history.  
Why it matters: Agent products need auditability.  
Initial approach: In-memory state.  
Exposed issue: Browser refresh erased story.  
How located: Persistence requirements and API tests.  
Final approach: SQLite repository with structured Task state.  
Trade-off: Local DB only, not production multi-user.  
Validation: Task list/detail APIs survive refresh.  
Interview line: Persistence is audit history here, not memory.

## 10. Proactive Trigger idempotency

Problem: Proactive triggers can duplicate tasks if fired repeatedly.  
Why it matters: Duplicate side effects are dangerous.  
Initial approach: Explicit tick.  
Exposed issue: Repeated tick and restart behavior needed checks.  
How located: Trigger Eval V1.  
Final approach: persisted trigger state, duplicate registration/fire prevention.  
Trade-off: No background scheduler in V1.  
Validation: Trigger Eval V1 reports duplicate prevention and restart idempotency at 1.000.  
Interview line: Proactive behavior must be idempotent before it becomes automatic.

## 11. Cross-device Context Continuity

Problem: A Task created on Phone was previously trapped on that client.  
Why it matters: Recreating it on Car would split history, context and confirmation state.  
Initial approach: Treat each device as a separate entry point.  
Exposed issue: A duplicate Task cannot prove continuity.  
Final approach: Persist a separate TaskDeviceState and minimized HandoffContext while keeping the original `task_id`.  
Trade-off: Coordination metadata and lifecycle must be maintained beside the Agent domain.  
Validation: Phone → Car → Phone view demo shows the same Task ID and reused context.  
Interview line: The Task owns context; a device only owns the current surface.

## 12. Multi-client Confirmation Consistency

Problem: Phone and Car can display the same pending confirmation concurrently.  
Why it matters: Two successful confirms could produce duplicate side effects.  
Initial approach: Rely on client button state.  
Exposed issue: UI state cannot serialize backend writes.  
Final approach: Atomically claim confirmation with `expected_version`; stale requests receive 409.  
Trade-off: Clients must reload after conflicts.  
Validation: Confirmation consistency test permits one transition and one side effect only.  
Interview line: HITL needs concurrency semantics, not just a confirmation button.

## 13. Device Offline Routing

Problem: A capability-compatible Car may be unavailable.  
Why it matters: Capability alone cannot justify a handoff recommendation.  
Initial approach: Route from static device type.  
Exposed issue: A stale device would receive an unusable handoff.  
Final approach: Heartbeat-derived presence with a deterministic 10-second timeout; offline targets are neither recommended nor accepted for creation.  
Trade-off: Local presence is intentionally simple and not distributed.  
Validation: Offline routing and handoff rejection cases score 1.000.  
Interview line: Routing requires availability plus capability plus Task context.

## 14. Optimistic Concurrency

Problem: Multiple clients can write Task coordination state from different versions.  
Why it matters: Silent last-write-wins can reverse ownership or repeat transitions.  
Initial approach: Update current device directly.  
Exposed issue: There was no stale-write signal.  
Final approach: Store Task version, require `expected_version`, update transactionally and return 409 on mismatch.  
Trade-off: Conflict handling becomes an explicit client responsibility.  
Validation: Version conflict, duplicate accept, restart and state-sync tests pass.  
Interview line: A small version integer creates a clear consistency contract for Portfolio V1.
