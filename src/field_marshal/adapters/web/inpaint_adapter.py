"""Inpaint web gateway adapter contract."""

from __future__ import annotations

from typing import Any


class InpaintAdapter:
    def submit_job(self, payload: dict[str, Any]) -> str:
        raise NotImplementedError

    def wait_for_completion(self, job_id: str) -> dict[str, Any]:
        raise NotImplementedError

    def download_outputs(self, job_id: str) -> list[str]:
        raise NotImplementedError

    def capture_evidence(self, job_id: str) -> dict[str, Any]:
        raise NotImplementedError
