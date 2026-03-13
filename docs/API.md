# Field Marshal Factory API (Phase 1)

## Health

- `GET /health`
- Returns service status and active DB path.

## Tasks

- `POST /api/tasks`
  - Body: `task_type`, `phase`, `input_payload`, optional `priority`, `assigned_to`, `max_retries`, `parent_task_id`
- `GET /api/tasks`
  - Query: optional `status`, `limit`
- `GET /api/tasks/{task_id}`
- `POST /api/tasks/{task_id}/transition`
  - Body: `to_status`, optional `reason_code`, `message`
- `POST /api/tasks/{task_id}/complete`
  - Body: `output_payload`
- `POST /api/tasks/{task_id}/fail`
  - Body: `reason_code`, optional `message`

## Reviews

- `GET /api/reviews`
- `POST /api/reviews/{review_id}/resolve`
  - Body: `resolution_notes`

## Notes

- API routes call services only.
- Services call repositories only.
- Repositories are the only store access layer.
