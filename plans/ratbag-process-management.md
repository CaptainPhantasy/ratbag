# Blueprint — RATBAG owns the process

Objective: **move process management out of a single function call and into the RATBAG server, so the web front end shows each step as it happens, lets the person revise before approving, and can cancel.**

Why now: the interview runs inside one blocking `POST /api/interview/run`. A front end that manages a process does not work that way, and anything that has to be babysat by a terminal is not a front end.

Source: generated with the `blueprint` skill pulled from the MCP gateway on 2026-10-27.

---

## Invariants (verified after every step)

1. `python3 -m unittest discover -s tests` passes.
2. No endpoint blocks for longer than one factory call (~a few seconds).
3. A step, once emitted, is never lost: replay from the last event id must reproduce the whole history.
4. Cancel leaves the workspace and the evidence intact.
5. The factory is never asked to do something the person did not answer.

## Dependency graph

```
S1 store ──▶ S2 events ──▶ S3 plan/approve/revise ──▶ S5 UI
   │             │                   │
   │             └──▶ S4 cancel      └──▶ S7 integration tests
   └──▶ S6 resume
                          S8 docs after S5
```

Parallel: S4 and S3 can proceed at the same time once S2 exists. S8 waits for S5.

---

## Step 1 — A job the server owns (strongest model)

**Context brief.** Today `Interview.run()` is called inside the HTTP handler and its steps are returned at the end. The caller sees nothing until everything is finished, and a dropped connection loses the work. The server needs a first-class job: an id, the answers, the session id once the factory assigns one, the step history, a status, and the tests and paths that come back.

**Tasks**
- Add `swarm/jobs.py`: `JobStore` over the existing SQLite file (`.swarm-data`), tables `jobs` and `job_events`.
- `create_job(answers) -> job`, `get_job(id)`, `list_jobs()`, `append_event(job_id, step)`, `set_status(job_id, status, detail)`.
- Statuses: `queued`, `planning`, `awaiting_approval`, `running`, `delivered`, `failed`, `cancelled`.
- Store answers as the tested `Answers.to_dict()`; never store keys or secrets.

**Verification**
- New `tests/test_jobs.py`: create, append, read back, status transitions, and a restart (new `JobStore` instance, same file) seeing the same history.
- `python3 -m unittest tests.test_jobs -v`

**Exit criteria.** A job survives a new process. No endpoint touches job state without going through the store.

**Rollback.** Delete `swarm/jobs.py`; nothing else imports it yet.

---

## Step 2 — Steps as they happen (default tier)

**Context brief.** The person needs to watch the factory work, one line at a time. The server has no event stream today. Server-sent events are enough: append-only, replayable from a cursor, and no WebSocket machinery.

**Tasks**
- `GET /api/jobs/<id>` returns the job and its steps.
- `GET /api/jobs/<id>/events?after=<n>` streams new steps as SSE, then keeps the connection open until the job ends.
- The runner writes each step through `JobStore.append_event` as it happens, not in a batch at the end.
- Event ids are monotonic per job; `after` replays deterministically.

**Verification**
- Start a job with the fake factory; `curl -N .../events?after=0` shows steps in order and closes when the job ends.
- Disconnect and reconnect with `after=<last>`; no step repeats and none are missing.

**Exit criteria.** A browser can render progress with no polling and no lost steps.

**Rollback.** The JSON endpoint remains; the SSE route can be removed without touching the store.

---

## Step 3 — Plan, approve and revise as separate decisions (strongest model)

**Context brief.** Approval is a decision, not a stage inside a run. The person must be able to see the plan, change one thing, see the new plan, and only then approve. The factory already supports `revise_intake_plan` and `approve_intake_plan`; the front end must expose them instead of collapsing them into `run()`.

**Tasks**
- `POST /api/jobs` creates a job and drafts the plan (factory `draft_intake_plan`), status `awaiting_approval`.
- `POST /api/jobs/<id>/revise` takes notes, calls `revise_intake_plan`, replaces the plan on the job.
- `POST /api/jobs/<id>/approve` calls `approve_intake_plan` and moves to `running`, which continues the pipeline from layout onward.
- The person's approval is recorded with `approved_by` naming the front end, never the operator silently.

**Verification**
- A test with the fake factory: draft → revise → approve, and the factory receives exactly one draft, one revise, one approve.
- A plan edited in the UI is not approved by accident: approve requires the plan hash the person saw.

**Exit criteria.** No path reaches `approve_intake_plan` without a prior plan the person saw.

**Rollback.** The old `/api/interview/run` stays until Step 5 lands.

---

## Step 4 — Cancel that actually stops (default tier)

**Context brief.** A cancel that only flips a flag leaves a builder running in the workspace. The factory's `execute_monitored_command` runs a child process; cancelling must reach it.

**Tasks**
- `POST /api/jobs/<id>/cancel` marks the job `cancelled` and signals the running subprocess group.
- The runner checks the job status between steps and stops at the next safe boundary.
- The workspace, the evidence written so far and the factory session id are kept and reported.

**Verification**
- A test with a builder that sleeps; cancel after 200 ms; the process is gone and the job is `cancelled`.
- The artifact directory is untouched by the cancel.

**Exit criteria.** No child outlives the job by more than a second.

**Rollback.** Remove the route; the flag check is harmless on its own.

---

## Step 5 — The page that manages (default tier)

**Context brief.** The current `web/interview.html` posts once and waits. It must become a workspace: form → plan → approve or revise → live steps → result, with the state owned by the job id in the URL.

**Tasks**
- Create the job, then render the plan with two buttons.
- Subscribe to `/events` with `EventSource`; render each step as it arrives.
- Keep the job id in the URL so a reload resumes the view.
- Show the cancel button while running; show the artifact path, deployed URL and manifest when delivered.
- Accessibility: focus order, labels, and a live region for step updates.

**Verification**
- Manual: run a page artifact through the browser; steps appear one by one; reload mid-run resumes; cancel leaves the workspace.
- No console errors; the page works with JavaScript only from the same origin.

**Exit criteria.** A person can complete the whole flow without a terminal.

**Rollback.** Keep `interview.html` until the new page passes the manual check.

---

## Step 6 — Survive a restart (default tier)

**Context brief.** A job whose server process restarts should be resumable: the factory keeps sessions on disk, so the front end can pick up where it stopped.

**Tasks**
- On startup, any job in `running` is marked `interrupted` with the last step preserved.
- `POST /api/jobs/<id>/resume` continues from the recorded stage, re-reading the factory session.
- Never re-run a step whose result is already recorded.

**Verification**
- Kill the server mid-run; restart; the job is `interrupted`; resume finishes it without duplicating steps.

**Exit criteria.** No duplicate factory calls after a restart.

**Rollback.** Jobs stay inspectable even if resume is removed.

---

## Step 7 — Integration tests against the real factory (default tier)

**Context brief.** The unit tests use a fake client. The chain must be proven against the running factory, or the fake is the only thing that works.

**Tasks**
- `tests/test_interview_integration.py`, skipped when `RATBAG_SDLC_COMMAND` cannot start.
- One run: create job, approve, deliver, assert the artifact path and the manifest exist.
- One cancel: assert the builder child is gone.

**Verification**
- `RATBAG_SDLC_INTEGRATION=1 python3 -m unittest tests.test_interview_integration -v`

**Exit criteria.** Green against the deployed factory; skipped cleanly when absent, never silently passing.

---

## Step 8 — Documentation (default tier)

**Tasks**
- README: the flow from the person's side, the endpoints from an operator's side.
- `docs/USER_MANUAL.md`: what each button does and what it refuses.
- A note that approval requires the plan the person saw, and why.

---

## Anti-patterns to avoid

- A job run inside the request handler, however convenient.
- Steps assembled after the fact and emitted as a list.
- Cancel implemented as a boolean nobody checks.
- The UI re-running a step on reconnect.
- Storing the person's approval as a side effect of clicking Run.
- A fake factory in every test and no real one anywhere.

## Mutation protocol

A step may be split, inserted, reordered or dropped only by editing this file and recording why in the same commit. A step that is dropped keeps its number and is marked `abandoned`, so the history stays readable.
