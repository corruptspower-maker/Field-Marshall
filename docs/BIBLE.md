# Field Marshal Factory Bible v1.0

This document is the canonical build doctrine for the Field Marshal Factory rewrite.

## 0. Purpose

Build a local video factory that:

1. Ingests source video.
2. Mines frames.
3. Indexes and retrieves candidate visuals.
4. Turns a concept into shot packets.
5. Edits stills through a web gateway.
6. Validates stills.
7. Turns stills into short clips through a web gateway.
8. Assembles clips into a final video.
9. Emits manifests and reports so each run is resumable and reproducible.

This system is a pipeline with controlled AI stages, not a single "AI that makes videos."

## 1. Non-Negotiable Laws

1. Manifest-first: no artifact exists without a persisted manifest record.
2. Persistent truth: database is authoritative; memory is cache.
3. Bounded roles: Planner plans, Critic critiques, Builders build, Gateways execute.
4. Resumable stages: every stage can restart from persisted state.
5. Adapters at edges: site/model/agent specifics stay outside core pipeline logic.
6. Retry with evidence: each retry records what failed and what changed.
7. Human review is a queue: repeated failures move to `awaiting_review`.
8. No god-objects: API != orchestration != persistence != UI.
9. One canonical boot path: one deterministic startup command.
10. Every stage emits artifacts: files, tests, outputs, and manifest samples.

## 2. Canonical Runtime Roles

- Human: provides concept and resolves escalated review items.
- Field Marshal / Planner: decomposes goals and dispatches bounded contracts.
- Lord / Critic: challenges evidence quality, does not mutate artifacts.
- Builder Agents: implement bounded contracts and emit evidence.
- Gateway Adapters: execute external web/service workflows and return structured results.
- Store: authoritative tasks/events/artifacts/evidence/retries/statuses.
- API/UI: uses service layer only, never business-brain logic.

## 3. Canonical Architecture

Human -> Field Marshal (planner) -> Task Service -> Store (SQLite first) ->
Workers/Builders/Gateways -> Artifacts + Events + Evidence -> QA/Critic ->
Approved assets or escalations -> Assembly + Reporting

The role logic from README is preserved, but runtime coupling is replaced with layered services.

## 4. Canonical Repository Shape

```text
Field-Marshall/
  src/field_marshal/
    api/
    core/
    services/
    store/
    adapters/
    factory/
    prompts/
    ui/
    utils/
  config/
    app.yaml
    services.yaml
    prompts.yaml
  data/
    registry.db
    manifests/
    logs/
    cache/
  assets/
    source_videos/
    normalized_videos/
    raw_frames/
    derived_images/
    generated_clips/
    normalized_clips/
    final_renders/
    reports/
  scripts/
    bootstrap.py
    dev_launch.py
    build_zip.py
  tests/
    unit/
    integration/
    e2e/
  docs/
    BIBLE.md
    TASK_CONTRACTS.md
    API.md
```

## 5. Canonical Persistent Objects

Minimum persisted objects:

- Task
- Artifact
- Event
- Review Item
- Scene Packet
- Clip Job

All records carry created/updated timestamps and stable IDs.

## 6. Canonical Task States

Allowed states:

- `pending`
- `queued`
- `claimed`
- `running`
- `awaiting_dependency`
- `awaiting_review`
- `succeeded`
- `failed_retryable`
- `failed_terminal`
- `cancelled`

Rules:

- Only workers move `claimed -> running`.
- Validation stages only succeed through validators.
- Repeated retry failures move to `awaiting_review`.
- Terminal failure requires a reason code.

## 7. Canonical Manifests

Every stage writes a manifest:

```json
{
  "id": "artifact_or_job_id",
  "stage": "detect|index|write|inpaint|qa|animate|assemble|report",
  "parent_id": "optional",
  "inputs": [],
  "outputs": [],
  "params": {},
  "status": "succeeded",
  "qa": {},
  "retry_count": 0,
  "timestamps": {
    "created_at": "",
    "updated_at": ""
  }
}
```

No stage is exempt.

## 8. Phase Doctrine

### Phase 1: Spine Rewrite

Objective:

- Replace prototype runtime with persistent layered architecture.

Deliverables:

- SQLite store and migrations.
- Task/event/artifact tables.
- State machine module.
- Service layer.
- Single bootstrap command.

Definition of done:

- Restart does not lose tasks/evidence.
- API reads/writes through store.
- No authoritative in-memory task dictionaries.
- No timing-based startup dependency.

### Phase 2-10

Implement ingestion, frame extraction, retrieval/index, writing/storyboard, inpaint gateway,
QA loop, animation gateway, normalization/assembly, and reporting with resumable manifests.

## 9. Field Marshal Operating Doctrine

Assignments are bounded contracts, not vague goals.

Required in every contract:

- Objective
- Exact files to touch
- Input contract
- Output contract
- Verification command
- Definition of done
- Refusal conditions
- Escalation conditions

Mandatory builder reply format:

- Files changed
- Commands run
- Tests run
- Result summary
- Sample artifact path
- Sample manifest snippet
- Blockers

## 10. Adapter Doctrine

LLM adapters expose:

- `generate(messages, config) -> response`
- `vision_review(image, rubric) -> structured verdict`

Agent adapters expose:

- `submit_task(contract) -> external_task_id`
- `poll_status(external_task_id) -> status`
- `fetch_result(external_task_id) -> result_bundle`

Web adapters expose:

- `submit_job(payload) -> job_id`
- `wait_for_completion(job_id) -> structured_status`
- `download_outputs(job_id) -> local_paths`
- `capture_evidence(job_id) -> screenshot_paths + notes`

Adapters never mutate store state directly; services persist adapter results.

## 11. Startup Doctrine

Forbidden:

- Hardcoded terminal profile dependencies.
- Multi-tab launcher as canonical startup.
- Sleep-based sequencing.

Required:

- One bootstrap script that validates config, initializes DB/migrations, verifies ports,
  starts API/workers, runs health checks, and optionally opens UI.

## 12. Testing Doctrine

- Unit: state transitions, repositories, manifest writers, retry logic.
- Integration: API <-> service <-> store and adapter <-> service.
- E2E: one small end-to-end factory run.

No stage is considered real without at least one unit test and one integration or acceptance test.

## 13. MVP Doctrine

MVP is:

- One source video.
- One concept.
- Three scenes.
- Frame extraction + retrieval.
- One edited start/end still per scene.
- One five-second clip per scene.
- Concatenated final output.
- Complete manifests + report bundle.

If this cannot run reliably, it is not yet a factory.

## 14. Out of Scope for v1

- Distributed workers.
- Redis/Celery/Kafka.
- Multi-user auth.
- Rich collaborative review system.
- Plugin marketplace.
- Full legal/provenance registry.

## 15. Migration Doctrine

Preserve:

- Role logic from README.
- Bondsman planning and Lord critique concept.
- Local-first philosophy.
- Safety/policy separation from execution.

Replace:

- Root-heavy runtime layout.
- In-memory authoritative state.
- Polling as architecture.
- Multi-tab launcher as startup spine.

## 16. Final Commandment

Build the spine first in this order:

1. Persistence
2. Layering
3. State machine
4. Deterministic bootstrap
5. Adapters
6. Factory stages
7. QA + reporting
8. Polish
