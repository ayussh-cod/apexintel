"""
backend/main.py
---------------
FastAPI backend — fully concurrent-safe.

Every pipeline run gets its own JobContext which carries:
  - isolated workspace directory
  - isolated ADK InMemorySessionService
  - isolated OTel TracerProvider → Phoenix Cloud project
  - isolated asyncio.Queue for SSE log delivery

No global state is mutated at runtime. Concurrent jobs cannot interfere.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import AsyncGenerator

# from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# load_dotenv()

# ── Resolve pipeline root ──────────────────────────────────────────────────
PIPELINE_ROOT = Path(__file__).resolve().parent.parent / "agents"
# sys.path.insert(0, str(PIPELINE_ROOT))

WORKSPACE_ROOT = PIPELINE_ROOT / "workspaces"
WORKSPACE_ROOT.mkdir(exist_ok=True)

PHOENIX_URL    = "https://app.phoenix.arize.com/s/job_searches"
TAVILY_API_KEY = os.environ["TAVILY_API_KEY"]

from job_context import make_context, JobContext  # noqa: E402


# ── Job registry ───────────────────────────────────────────────────────────
# Dict is only appended to (never mutated per-key after creation),
# so reads are safe without a lock in CPython's GIL.
# For multi-process deployments replace with Redis / a DB.
class JobStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"


class JobRecord(BaseModel):
    id:           str
    field:        str
    status:       JobStatus  = JobStatus.PENDING
    created_at:   str        = ""
    completed_at: str | None = None
    error:        str | None = None
    phoenix_url:  str | None = None

    class Config:
        use_enum_values = True


_registry: dict[str, JobRecord]  = {}   # job_id → record (write-once per key)
_contexts: dict[str, JobContext] = {}   # job_id → context (write-once per key)


# ── FastAPI app ────────────────────────────────────────────────────────────
app = FastAPI(title="ApexIntel Pipeline API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / response schemas ─────────────────────────────────────────────
class RunRequest(BaseModel):
    field: str


# ── Pipeline background task ───────────────────────────────────────────────
async def _run_pipeline(job_id: str) -> None:
    rec = _registry[job_id]
    ctx = _contexts[job_id]

    rec.status = JobStatus.RUNNING

    try:
        # ── Step 1 ────────────────────────────────────────────────────────
        await ctx.emit("info", "━━ Step 1/3 — Querying Agent ━━")
        from querying_agent import run_querying_agent  # noqa: PLC0415
        await run_querying_agent(ctx, TAVILY_API_KEY)

        # ── Step 2 ────────────────────────────────────────────────────────
        await ctx.emit("info", "━━ Step 2/3 — URL Extractor ━━")
        from tavily_extractor import run_extractor  # noqa: PLC0415
        await run_extractor(ctx, TAVILY_API_KEY)

        # ── Step 3 ────────────────────────────────────────────────────────
        await ctx.emit("info", "━━ Step 3/3 — Synthesizer Agent ━━")
        from synthesizer_agent import run_synthesizer  # noqa: PLC0415
        await run_synthesizer(ctx)

        # ── Done ──────────────────────────────────────────────────────────
        rec.status       = JobStatus.COMPLETED
        rec.completed_at = datetime.now(timezone.utc).isoformat()
        await ctx.emit("done", f"Pipeline complete! Traces → {ctx.phoenix_url}")

    except Exception as exc:
        rec.status = JobStatus.FAILED
        rec.error  = str(exc)
        await ctx.emit("error", f"Pipeline failed: {exc}")

    finally:
        await ctx.close_stream()


# ── Routes ─────────────────────────────────────────────────────────────────
@app.post("/api/run", status_code=202)
async def start_pipeline(req: RunRequest, background_tasks: BackgroundTasks):
    if not req.field.strip():
        raise HTTPException(400, "field cannot be empty")

    job_id = str(uuid.uuid4())
    # ctx    = make_context(job_id, req.field.strip(), WORKSPACE_ROOT)
    ctx = make_context(job_id, req.field.strip())    

    rec = JobRecord(
        id=job_id,
        field=req.field.strip(),
        created_at=datetime.now(timezone.utc).isoformat(),
        phoenix_url=ctx.phoenix_url,
    )
    _registry[job_id] = rec
    _contexts[job_id] = ctx

    background_tasks.add_task(_run_pipeline, job_id)
    return {"job_id": job_id, "status": "pending", "phoenix_url": ctx.phoenix_url}


@app.get("/api/stream/{job_id}")
async def stream_logs(job_id: str):
    if job_id not in _registry:
        raise HTTPException(404, "Job not found")

    ctx = _contexts[job_id]

    async def event_generator() -> AsyncGenerator[str, None]:
        # Replay buffered logs first (supports SSE reconnection)
        for line in list(ctx.log_buffer):
            yield f"data: {line}\n\n"

        # Stream live
        while True:
            item = await ctx.log_queue.get()
            if item is None:
                yield 'data: {"level":"close"}\n\n'
                break
            yield f"data: {item}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/jobs")
async def list_jobs():
    return sorted(_registry.values(), key=lambda r: r.created_at, reverse=True)


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    rec = _registry.get(job_id)
    if not rec:
        raise HTTPException(404, "Job not found")
    return rec


@app.get("/api/notes/{job_id}")
async def get_notes(job_id: str):
    rec = _registry.get(job_id)
    if not rec:
        raise HTTPException(404, "Job not found")
    if rec.status != JobStatus.COMPLETED:
        raise HTTPException(400, f"Job is {rec.status} — notes not ready yet")

    # vault = _contexts[job_id].vault_dir
    # if not vault.exists():
    #     raise HTTPException(404, "Vault directory missing")
    ctx   = _contexts[job_id]
    files = ctx.list_vault_files()

    # def _tree(path: Path) -> dict:
    #     if path.is_file():
    #         return {"name": path.name, "type": "file",
    #                 "content": path.read_text(encoding="utf-8")}
    #     return {
    #         "name": path.name, "type": "dir",
    #         "children": [
    #             _tree(c) for c in sorted(path.iterdir())
    #             if not c.name.startswith(".")
    #         ],
    #     }

    # return _tree(vault)
    tree: dict = {"name": "vault", "type": "dir", "children": []}

    for path in sorted(files):
        parts   = path.split("/")
        content = ctx.read_vault_file(path)
        node    = tree

        for i, part in enumerate(parts[:-1]):      # walk/create intermediate dirs
            existing = next((c for c in node["children"] if c["name"] == part), None)
            if not existing:
                existing = {"name": part, "type": "dir", "children": []}
                node["children"].append(existing)
            node = existing

        node["children"].append({"name": parts[-1], "type": "file", "content": content})

    return tree


@app.delete("/api/jobs/{job_id}", status_code=204)
async def delete_job(job_id: str):
    if job_id not in _registry:
        raise HTTPException(404, "Job not found")
    _registry.pop(job_id, None)
    _contexts.pop(job_id, None)


@app.get("/api/health")
async def health():
    return {
        "status":     "ok",
        "phoenix":    PHOENIX_URL,
        "jobs_total": len(_registry),
    }
