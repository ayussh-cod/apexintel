"""
job_context.py
--------------
The single source of truth for all per-job state.

A JobContext is created once per pipeline run and passed explicitly
into every agent function. Nothing is read from or written to:
  - os.environ
  - module-level globals
  - shared singletons

This makes concurrent runs completely isolated from each other.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from google.adk.sessions import InMemorySessionService
from opentelemetry import trace as otel_trace
from phoenix.otel import register
from google.cloud import storage

PHOENIX_API_KEY = os.environ["PHOENIX_API_KEY"]
GCS_BUCKET_NAME = os.environ["GCS_BUCKET_NAME"] 
PHOENIX_BASE    = "https://app.phoenix.arize.com/s/job_searches"
GEMINI_MODEL    = "gemini-2.5-flash"
QUALITY_THRESHOLD   = 0.70
MAX_RETRIES         = 3
MAX_NAMES           = 5
MAX_CONTENT_CHARS   = 14_000
STRUCTURE_PASS_SCORE = 0.80

_tracer_provider = register(
    project_name="apex-pipeline",
    auto_instrument=True,
    endpoint=f"{PHOENIX_BASE}/v1/traces",
    headers={"api_key": PHOENIX_API_KEY},
)



@dataclass
class JobContext:
    """
    Encapsulates everything that is unique to one pipeline run.

    Passed by reference into every agent/extractor function.
    Never stored in module globals.
    """

    job_id:          str
    field_name:      str
    # workspace:       Path            # job-scoped directory for all files
    phoenix_project: str             # isolated Phoenix project name,
    _bucket:         storage.Bucket = field(init=False, repr=False)

    # Per-job OTel tracer — does NOT touch the global TracerProvider
    tracer:          otel_trace.Tracer = field(init=False)

    # Per-job ADK session service — no sharing between runs
    session_service: InMemorySessionService = field(init=False)

    # SSE log queue — populated by emit(), consumed by the SSE endpoint
    log_queue:       asyncio.Queue = field(default_factory=asyncio.Queue)

    # Append-only log buffer for replay on SSE reconnect
    log_buffer:      list[str] = field(default_factory=list)

    import asyncio

    def __post_init__(self) -> None:
        client = storage.Client()
        self._bucket = client.bucket(GCS_BUCKET_NAME)
        # self.workspace.mkdir(parents=True, exist_ok=True)
        self.tracer = _tracer_provider.get_tracer(f"pipeline")

        self.session_service = InMemorySessionService()

    # ── Convenience paths ──────────────────────────────────────────────
    # @property
    # def querying_path(self) -> Path:
    #     return self.workspace / "querying_output.json"

    # @property
    # def extracted_path(self) -> Path:
    #     return self.workspace / "extracted_content.json"

    # @property
    # def vault_dir(self) -> Path:
    #     return self.workspace / "obsidian_vault"

    @property
    def phoenix_url(self) -> str:
        return f"{PHOENIX_BASE}/projects/{self.phoenix_project}"

    QUERYING_FILE  = "querying_output.json"
    EXTRACTED_FILE = "extracted_content.json"

    @property
    def _prefix(self) -> str:
        return f"jobs/{self.job_id}"


    def write_file(self, filename: str, content: str) -> None:
        blob = self._bucket.blob(f"{self._prefix}/{filename}")
        blob.upload_from_string(content, content_type="application/json")

    def read_file(self, filename: str) -> str:
        blob = self._bucket.blob(f"{self._prefix}/{filename}")
        return blob.download_as_text()

    def write_vault_file(self, relative_path: str, content: str) -> None:
        blob = self._bucket.blob(f"{self._prefix}/vault/{relative_path}")
        blob.upload_from_string(content, content_type="text/markdown")

    def list_vault_files(self) -> list[str]:
        prefix = f"{self._prefix}/vault/"
        blobs  = self._bucket.client.list_blobs(GCS_BUCKET_NAME, prefix=prefix)
        return [b.name.removeprefix(prefix) for b in blobs]

    def read_vault_file(self, relative_path: str) -> str:
        blob = self._bucket.blob(f"{self._prefix}/vault/{relative_path}")
        return blob.download_as_text()

    # ── Logging ────────────────────────────────────────────────────────
    async def emit(self, level: str, message: str) -> None:
        line = json.dumps({
            "ts":    datetime.now(timezone.utc).isoformat(),
            "level": level,
            "msg":   message,
        })
        self.log_buffer.append(line)
        await self.log_queue.put(line)

    async def close_stream(self) -> None:
        """Signal the SSE generator to close."""
        await self.log_queue.put(None)


def make_context(job_id: str, field_name: str) -> JobContext:
    """Factory — creates a fresh, fully isolated JobContext."""
    # workspace = workspace_root / job_id
    return JobContext(
        job_id=job_id,
        field_name=field_name,
        # workspace=workspace,
        phoenix_project=f"apex-pipeline",
    )
