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

PHOENIX_API_KEY = os.environ["PHOENIX_API_KEY"]
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
    workspace:       Path            # job-scoped directory for all files
    phoenix_project: str             # isolated Phoenix project name

    # Per-job OTel tracer — does NOT touch the global TracerProvider
    tracer:          otel_trace.Tracer = field(init=False)

    # Per-job ADK session service — no sharing between runs
    session_service: InMemorySessionService = field(init=False)

    # SSE log queue — populated by emit(), consumed by the SSE endpoint
    log_queue:       asyncio.Queue = field(default_factory=asyncio.Queue)

    # Append-only log buffer for replay on SSE reconnect
    log_buffer:      list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.tracer = _tracer_provider.get_tracer(f"pipeline")

        self.session_service = InMemorySessionService()

    # ── Convenience paths ──────────────────────────────────────────────
    @property
    def querying_path(self) -> Path:
        return self.workspace / "querying_output.json"

    @property
    def extracted_path(self) -> Path:
        return self.workspace / "extracted_content.json"

    @property
    def vault_dir(self) -> Path:
        return self.workspace / "obsidian_vault"

    @property
    def phoenix_url(self) -> str:
        return f"{PHOENIX_BASE}/projects/{self.phoenix_project}"

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


def make_context(job_id: str, field_name: str, workspace_root: Path) -> JobContext:
    """Factory — creates a fresh, fully isolated JobContext."""
    workspace = workspace_root / job_id
    return JobContext(
        job_id=job_id,
        field_name=field_name,
        workspace=workspace,
        phoenix_project=f"apex-{job_id[:8]}",
    )
