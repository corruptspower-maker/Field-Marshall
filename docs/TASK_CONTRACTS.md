# Field Marshal Task Contracts (First 10)

This is the initial execution set for the Phase 1 spine rewrite.

## Contract 01

Task ID: FM-P1-001  
Phase: 1 (Spine Rewrite)  
Objective: Create canonical repository scaffolding and package boundaries under `src/field_marshal`.  
Files to touch: `src/field_marshal/**/__init__.py`, `config/`, `data/`, `assets/`, `tests/`  
Inputs: Existing prototype repository root  
Outputs: New layered folder structure with importable packages  
Constraints: No runtime logic in package init files  
Tests required: N/A (structure-only)  
Definition of done: Directories exist and `python -c "import field_marshal"` works with `PYTHONPATH=src`  
Escalate if: Existing files conflict with required package names  
Do not: Move or delete prototype runtime files in this task

## Contract 02

Task ID: FM-P1-002  
Phase: 1 (Spine Rewrite)  
Objective: Implement SQLite database bootstrap and migration runner.  
Files to touch: `src/field_marshal/store/db.py`, `src/field_marshal/store/migrations.py`  
Inputs: `config/app.yaml` DB path  
Outputs: Deterministic DB initialization and idempotent migrations  
Constraints: SQLite only; no ORM  
Tests required: Unit test for idempotent migration run  
Definition of done: Running bootstrap twice preserves schema and data  
Escalate if: Migration cannot be made idempotent without destructive SQL  
Do not: Store authoritative runtime state in memory

## Contract 03

Task ID: FM-P1-003  
Phase: 1 (Spine Rewrite)  
Objective: Define canonical persisted models for Task, Artifact, Event, ReviewItem, ScenePacket, ClipJob, Manifest.  
Files to touch: `src/field_marshal/store/models.py`, `src/field_marshal/store/migrations.py`  
Inputs: Bible section "Canonical persistent objects"  
Outputs: Model dataclasses and matching SQL table definitions  
Constraints: Use ISO-8601 UTC timestamps  
Tests required: Unit test for model serialization round-trip  
Definition of done: Models map 1:1 with DB tables  
Escalate if: Any required field cannot be represented cleanly in SQLite  
Do not: Hide fields inside unstructured text blobs unless defined as `*_json`

## Contract 04

Task ID: FM-P1-004  
Phase: 1 (Spine Rewrite)  
Objective: Implement state machine with canonical statuses and transition guards.  
Files to touch: `src/field_marshal/core/state_machine.py`  
Inputs: Bible section "Canonical task states"  
Outputs: Transition validation API (`can_transition`, `enforce_transition`)  
Constraints: Terminal failures must require reason code  
Tests required: Unit tests for valid and invalid transitions  
Definition of done: Illegal transitions fail fast with explicit error  
Escalate if: A required transition is ambiguous in doctrine  
Do not: Perform persistence in state machine module

## Contract 05

Task ID: FM-P1-005  
Phase: 1 (Spine Rewrite)  
Objective: Build repository layer for tasks, artifacts, events, manifests, and review items.  
Files to touch: `src/field_marshal/store/repositories/*.py`  
Inputs: Models + DB module  
Outputs: CRUD repositories with typed return models  
Constraints: Repository methods only; no business orchestration  
Tests required: Unit tests for create/get/list/update operations  
Definition of done: Repositories are the only store access point used by services  
Escalate if: Cross-table transaction semantics are unclear  
Do not: Access SQLite directly from API routes

## Contract 06

Task ID: FM-P1-006  
Phase: 1 (Spine Rewrite)  
Objective: Implement service layer (`task_service`, `artifact_service`, `evidence_service`, `review_service`).  
Files to touch: `src/field_marshal/services/*.py`  
Inputs: Repositories + state machine  
Outputs: Business operations with event emission and retry accounting  
Constraints: Services own orchestration; adapters return data only  
Tests required: Integration test for task lifecycle and retry-to-review escalation  
Definition of done: Service calls persist state transitions and evidence events  
Escalate if: Retry policy conflicts with state machine constraints  
Do not: Put route/request logic into services

## Contract 07

Task ID: FM-P1-007  
Phase: 1 (Spine Rewrite)  
Objective: Add manifest writer workflow enforcing manifest-first artifact tracking.  
Files to touch: `src/field_marshal/services/artifact_service.py`, `data/manifests/`  
Inputs: Stage input/output metadata  
Outputs: Manifest JSON files and persisted manifest records  
Constraints: Every write must include timestamps and stage name  
Tests required: Unit test for manifest file + DB record creation  
Definition of done: Artifact registration fails if manifest write fails  
Escalate if: Manifest schema needs version negotiation  
Do not: Create orphaned artifacts without manifest IDs

## Contract 08

Task ID: FM-P1-008  
Phase: 1 (Spine Rewrite)  
Objective: Implement Flask API app using services (not process globals).  
Files to touch: `src/field_marshal/api/app.py`, `src/field_marshal/api/routes/*.py`  
Inputs: Service layer interfaces  
Outputs: `/health`, task CRUD/transition endpoints, review queue endpoints  
Constraints: Routes call services only  
Tests required: Integration test API -> service -> store flow  
Definition of done: API restart keeps prior tasks and events  
Escalate if: Endpoint contracts need versioning before release  
Do not: Reintroduce in-memory authoritative task dictionaries

## Contract 09

Task ID: FM-P1-009  
Phase: 1 (Spine Rewrite)  
Objective: Create deterministic single-entry bootstrap command.  
Files to touch: `scripts/bootstrap.py`, `config/app.yaml`, `config/services.yaml`, `config/prompts.yaml`  
Inputs: App config and service config  
Outputs: One command that validates config, initializes DB, verifies port, starts API  
Constraints: No arbitrary sleep-based sequencing  
Tests required: Script-level smoke check in CI or local command verification  
Definition of done: `python scripts/bootstrap.py` starts the new spine consistently  
Escalate if: Port verification cannot be made cross-platform  
Do not: Depend on Windows Terminal tab profiles

## Contract 10

Task ID: FM-P1-010  
Phase: 1 (Spine Rewrite)  
Objective: Establish baseline test suites and reproducibility fixtures.  
Files to touch: `tests/unit/`, `tests/integration/`, `tests/e2e/`  
Inputs: New services and API  
Outputs: Initial passing unit and integration tests, e2e placeholder harness  
Constraints: Tests must run against temp SQLite DB by default  
Tests required: At least one state machine unit test and one integration lifecycle test  
Definition of done: `pytest tests/unit tests/integration` passes locally  
Escalate if: Test environment lacks required runtime dependency  
Do not: Use live external gateways in Phase 1 test suite
