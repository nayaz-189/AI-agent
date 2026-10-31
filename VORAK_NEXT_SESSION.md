VORAK DEVELOPMENT CHECKPOINT

CURRENT WORKING SYSTEM:
- Gemini Live voice conversation restored.
- Windows application launching works.
- Owner voice authentication remains unresolved.
- General in-app automation needs live validation.

NEXT IMPLEMENTATIONS:
1. Timed whole-display access (30 seconds to 60 minutes).
2. Independent web research, live weather and news.
3. Faster app and website automation.
4. WhatsApp and other in-app interactions.
5. Reduce loading delays and repeated initialization.
6. New audio-version feature (details to finalize).
7. Full regression testing before installing new patches.

IMPORTANT:
Do not overwrite the working Gemini Live runtime.
Do not delete existing folders without auditing dependencies.

OCTOBER 31, 2026 — VERIFIED FIELD OBSERVATIONS
- Gemini Live successfully conversed through Puck, opened Calculator, fetched current weather, and retrieved recent news headlines on Windows.
- General web browsing has had some successful interactive operation but verification and latency remain inconsistent.
- Basic weather/headline research works; headline summaries are not full-article fact checking. Reject invented product names or unverified claims.
- Owner/speaker authority is not reliably enforced yet; phantom/incorrectly attributed speech remains a problem.
- An opt-in expert connector and headset interruption prototype exist on feature branches; neither constitutes a fully validated deep-research or multitasking system.
- Do not interpret a source-only checklist change as an implementation or successful test.

DEFERRED MULTITASKING AND AGENT ORCHESTRATION — ROADMAP, NOT IMPLEMENTED
Goal: VORAK remains responsive to new voice/chat questions while complex work continues, rather than occupying the only conversational channel until a job is done.

1. Durable task orchestrator: a coordinator with concurrent, isolated worker agents, an async job queue, a configurable target of 10–15 simultaneous tasks, fairness, prioritization, backpressure, concurrency caps, rate limits, and per-task resource/cost budgets. The target is a design goal, not a guarantee that 15 heavy model or UI jobs can run at once.
2. Always-responsive conversation agent: a voice assistant/dispatcher stays available during worker execution and can answer unrelated questions, accept new jobs, and report what is running, without cancelling or blocking existing authorized work.
3. Task lifecycle and observability: give each job an ID, owner request, scope, permissions, dependencies, status (queued/running/waiting/blocked/completed/failed/cancelled), checked milestones, logs, source/artifact references, and explicitly reported uncertainty. On demand: "what's the progress of task X?" with factual progress; optional meaningful milestone notifications without monopolizing the microphone.
4. Reliable control semantics: "stop speaking" cuts playback; "cancel task X" cancels only that job and its authorized descendants; "pause/resume task X" affects that job; "stop VORAK" ends the session according to confirmation policy. Cancellation of external actions is best-effort; never misreport an irreversible or pending action as cancelled.
5. Multi-step build workflow: a planner produces requirements/problem framing, feasibility and constraints, research, architecture, implementation, tests, deployment/checks and an evidence-based delivery report. Separate agents can handle these stages in parallel where dependencies permit; keep the user informed when requested while work is ongoing.
6. Model/tool registry: one organized configuration area for all providers, tools, capabilities, model metadata, pricing, latency, permissions and fallback policy, with distinct research and general-purpose model groups. Build a curated pool of roughly 7–8 suitable models per task domain and route to the best available model(s) by capability, measured quality, speed, cost, context size and privacy. Do not blindly call all models for every task; consensus or multi-model review only when worthwhile.
7. Specialist teams: distinct research, coding, browsing/UI, verification, summarization and planning workers with scoped permissions and shared task state. Coordinators may delegate, but outputs must be checked; the chat model must never invent completion or evidence.
8. Deferred expert research stack: evaluate/conditionally integrate Perplexity, Hermes Agent, Google Gemini Deep Research and notebook/document research services, with other research models as appropriate. Keep this distinct from basic weather/news lookup. Require source provenance, cross-source verification, citations, recency filters, claim checking and research depth/cost controls.
9. Persisted continuity: recover active job manifests after restart, reconcile external state before resuming, prevent duplicate side effects, and maintain an auditable timeline without exposing sensitive voice samples, browser credentials or financial data.
10. Acceptance criteria: concurrent conversation while work runs; meaningful task IDs/status and partial reports; task-specific interruption; 10–15 simulated-job scheduling stress tests plus realistic resource-limited end-to-end trials; no duplicate app actions; reliable owner authorization; documented rollback paths.
11. Measure performance: voice response latency, first app index load, task queue delay, worker wall time, compute/API spend, model reliability and failed-tool recovery. No repeated full rescans or unnecessary model calls.

TIMING AND SCOPE
- This section is a future implementation checklist only; DO NOT install or launch new orchestration agents today.
- Complete voice reliability/security, app-action verification, and current small-tool regressions first.
- Preserve the known-working Gemini Live checkpoint and use separate feature branches, tests and rollback for new features.

NOVEMBER CONVERSATION CONTROL EXPERIMENT — NOT YET VALIDATED ON WINDOWS
- Speech-only STOP: discard audible response and remain silent for a new utterance; NEVER cancel running desktop/research work.
- PAUSE/WAIT 10/20/30 seconds: temporary listening window, best-effort combined follow-up response when time expires; explicit CONTINUE resumes earlier. No guarantee that separately detected Live speech turns merge correctly.
- While audio is playing, spoken interruption requires opt-in headset barge-in; default laptop-speaker mode intentionally mutes mic to prevent echo/false activations.
- Future concurrent task STOP/PAUSE/RESUME by task ID is deferred to the multi-agent orchestrator and requires separate cancellation/permission semantics.
- Regression and Windows microphone tests are mandatory before merging.
