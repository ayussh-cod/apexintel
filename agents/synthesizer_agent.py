"""
synthesizer_agent.py
--------------------
Google ADK + Gemini synthesizer.

All vault paths come from ctx.vault_dir — no VAULT_DIR global,
no module-level mutation. Safe for concurrent jobs.

Public API:
    run_synthesizer(ctx: JobContext) -> None
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from pathlib import Path

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.genai.types import Content, Part

from job_context import (
    JobContext,
    GEMINI_MODEL,
    MAX_CONTENT_CHARS,
    STRUCTURE_PASS_SCORE,
)


# ── Stateless ADK agent definitions ───────────────────────────────────────
_overview_agent = LlmAgent(
    name="overview_agent",
    model=GEMINI_MODEL,
    instruction="""
You are an expert knowledge curator creating Obsidian Markdown notes.

Always produce the following EXACT structure (all sections required):

---
tags: [top-performer, <field>, strategy]
aliases: ["<Name>"]
field: <field>
created: <ISO date>
---

# <Name> — Strategy Overview

## Background
(2-3 sentences)

## Core Strategy
(prose, ≥3 sentences)

## Key Principles
(4-6 bullet points)

## Unique Edge
(what sets them apart)

## Lessons for Practitioners
(2-3 second-person lessons)

Rules: Use [[wikilinks]]. No commentary outside structure. Second-person for actionable advice.
""",
)

_tasks_agent = LlmAgent(
    name="tasks_agent",
    model=GEMINI_MODEL,
    instruction="""
You are an expert productivity coach creating Obsidian action-task notes.

Always produce this EXACT structure:

# <Name> — Actionable Tasks

> Derived from the strategy of <Name> in <field>.

## Phase 1 — Foundation (Week 1-2)
- [ ] <concrete task>
(≥5 tasks)

## Phase 2 — Build (Week 3-6)
- [ ] <concrete task>
(≥5 tasks)

## Phase 3 — Compound (Month 2-3)
- [ ] <concrete task>
(≥5 tasks)

## Daily / Weekly Rituals
- [ ] <ritual>
(≥3 items)

## Metrics to Track
| Metric | Target | Frequency |
|--------|--------|-----------|
| <item> | <val>  | <freq>    |
(≥3 rows)

Rules: Every task must start with `- [ ]`. Be concrete — never vague.
""",
)

_sources_agent = LlmAgent(
    name="sources_agent",
    model=GEMINI_MODEL,
    instruction="""
You are a research librarian creating an Obsidian sources note.

Always produce this EXACT structure:

# <Name> — Sources

## Sources

### [<Title or URL>](<URL>)
- **Key insight**: <one-sentence takeaway>
- **Relevance**: <why this source matters>

(one entry per URL)

Rules: Include ALL URLs. Mark failed ones as "⚠ Extraction failed".
""",
)

_validator_agent = LlmAgent(
    name="validator_agent",
    model=GEMINI_MODEL,
    instruction="""
You are an Obsidian Markdown structure auditor.
Score structural completeness on 0.0-1.0. Respond ONLY with valid JSON (no fences):
{"score": <float>, "missing": ["<element>"], "reason": "<brief>"}
""",
)

_repair_agent = LlmAgent(
    name="repair_agent",
    model=GEMINI_MODEL,
    instruction="""
You are an Obsidian Markdown repair specialist.
Rewrite a structurally incomplete note so it fully complies with the required structure.
Output ONLY the corrected Markdown — no explanation.
""",
)

REQUIRED_ELEMENTS = {
    "overview": ["tags:", "aliases:", "## Background", "## Core Strategy",
                 "## Key Principles", "## Unique Edge", "## Lessons"],
    "tasks":    ["- [ ]", "## Phase 1", "## Phase 2", "## Phase 3",
                 "## Daily", "## Metrics", "| Metric |"],
    "sources":  ["## Sources", "### [", "Key insight", "Relevance"],
}


# ── Per-invocation runner helper ───────────────────────────────────────────
async def _run_agent(ctx: JobContext, agent: LlmAgent, prompt: str, max_tokens: int = 3000) -> str:
    runner  = Runner(
        agent=agent,
        app_name=f"{agent.name}.{ctx.job_id}",
        session_service=ctx.session_service,
    )
    session = await ctx.session_service.create_session(
        app_name=f"{agent.name}.{ctx.job_id}",
        user_id=ctx.job_id,
    )
    content = Content(role="user", parts=[Part(text=prompt)])
    final   = ""

    async for event in runner.run_async(
        user_id=ctx.job_id,
        session_id=session.id,
        new_message=content,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final = "".join(
                p.text for p in event.content.parts
                if hasattr(p, "text") and p.text
            )

    return final.strip()


# ── Validation & repair ────────────────────────────────────────────────────
async def _validate(ctx: JobContext, note_type: str, content: str) -> tuple[float, list[str]]:
    required  = REQUIRED_ELEMENTS.get(note_type, [])
    hits      = sum(1 for k in required if k in content)
    heuristic = hits / max(len(required), 1)

    prompt = (
        f"Note type: {note_type}\n"
        f"Required elements: {required}\n\n"
        f"Note (first 2000 chars):\n{content[:2000]}"
    )
    raw = await _run_agent(ctx, _validator_agent, prompt, max_tokens=256)
    raw = raw.strip().lstrip("```json").rstrip("```").strip()
    try:
        data    = json.loads(raw)
        llm_s   = float(data.get("score", heuristic))
        missing = data.get("missing", [])
        score   = (heuristic + llm_s) / 2
    except Exception:
        score, missing = heuristic, []

    return score, missing


async def _validate_and_repair(
    ctx: JobContext,
    note_type: str,
    content: str,
    original_instruction: str,
    original_prompt: str,
) -> str:
    with ctx.tracer.start_as_current_span(f"validate-{note_type}") as span:
        span.set_attribute("job_id", ctx.job_id)
        score, missing = await _validate(ctx, note_type, content)
        span.set_attribute("structure_score", score)
        span.set_attribute("passed", score >= STRUCTURE_PASS_SCORE)

        if score >= STRUCTURE_PASS_SCORE:
            return content

        await ctx.emit("info", f"    ⚠ {note_type} score={score:.2f}, repairing (missing={missing})")

        repair_prompt = (
            f"ORIGINAL INSTRUCTIONS:\n{original_instruction}\n\n"
            f"VALIDATION REPORT: score={score:.2f}, missing={missing}\n\n"
            f"CONTEXT:\n{original_prompt[:2000]}\n\n"
            "Rewrite the note to include ALL required elements."
        )
        repaired    = await _run_agent(ctx, _repair_agent, repair_prompt, max_tokens=3000)
        new_score, _ = await _validate(ctx, note_type, repaired)
        span.set_attribute("repaired_score", new_score)
        await ctx.emit("info", f"    ✓ repaired score={new_score:.2f}")
        return repaired


# ── Note builders (each takes ctx explicitly) ──────────────────────────────
def _trunc(text: str, n: int = MAX_CONTENT_CHARS) -> str:
    return text[:n] + ("\n…[truncated]" if len(text) > n else "")


async def _build_overview(ctx: JobContext, name: str, combined: str) -> str:
    prompt  = f"Name: {name}\nField: {ctx.field_name}\n\nSource material:\n{combined}"
    content = await _run_agent(ctx, _overview_agent, prompt, max_tokens=2500)
    return await _validate_and_repair(
        ctx, "overview", content, _overview_agent.instruction or "", prompt
    )


async def _build_tasks(ctx: JobContext, name: str, combined: str) -> str:
    prompt  = f"Name: {name}\nField: {ctx.field_name}\n\nSource material:\n{combined}"
    content = await _run_agent(ctx, _tasks_agent, prompt, max_tokens=2500)
    return await _validate_and_repair(
        ctx, "tasks", content, _tasks_agent.instruction or "", prompt
    )


async def _build_sources(ctx: JobContext, name: str, pages: list[dict]) -> str:
    entries = []
    for p in pages:
        snippet = _trunc(p.get("raw_content", ""), 400) if not p.get("failed") else ""
        entries.append(
            f"URL: {p['url']}\nStatus: {'FAILED' if p.get('failed') else 'OK'}\nSnippet: {snippet}"
        )
    prompt  = f"Name: {name}\n\n" + "\n---\n".join(entries)
    content = await _run_agent(ctx, _sources_agent, prompt, max_tokens=2000)
    return await _validate_and_repair(
        ctx, "sources", content, _sources_agent.instruction or "", prompt
    )


# ── Vault writer ───────────────────────────────────────────────────────────
def _slug(text: str) -> str:
    return re.sub(r"[^\w\s-]", "", text).strip().replace(" ", "_")


def _write_index(vault: Path, field_name: str, names: list[str]) -> None:
    links = "\n".join(f"- [[{n}/overview|{n}]]" for n in names)
    (vault / "_index.md").write_text(
        f"---\ntags: [MOC, top-performers, {field_name.replace(' ','-')}]\n---\n\n"
        f"# Top Performers in {field_name.title()} — Map of Content\n\n"
        f"## Performers\n{links}\n",
        encoding="utf-8",
    )


@dataclass
class _PerformerNotes:
    name: str
    overview: str
    tasks: str
    sources: str


# ── Public entry point ─────────────────────────────────────────────────────
async def run_synthesizer(ctx: JobContext) -> None:
    """
    Reads ctx.extracted_path, writes vault to ctx.vault_dir.
    All paths are job-scoped. Safe for concurrent execution.
    """
    with open(ctx.extracted_path) as f:
        data = json.load(f)

    field_name = data["field"]
    performers = data["performers"]
    vault      = ctx.vault_dir
    vault.mkdir(parents=True, exist_ok=True)

    await ctx.emit("info", f"Synthesizer started — {len(performers)} performers")

    all_notes: list[_PerformerNotes] = []

    for p in performers:
        name  = p["name"]
        pages = p.get("pages", [])

        if not pages:
            await ctx.emit("info", f"  {name}: no pages, skipping")
            continue

        with ctx.tracer.start_as_current_span(f"synthesise-{name}") as span:
            span.set_attribute("job_id",     ctx.job_id)
            span.set_attribute("name",       name)
            span.set_attribute("page_count", len(pages))

            await ctx.emit("info", f"  Synthesising {name}…")

            good   = [pg for pg in pages if not pg.get("failed") and pg.get("raw_content")]
            per    = MAX_CONTENT_CHARS // max(len(good), 1)
            combined = _trunc(
                "\n\n---\n\n".join(_trunc(pg["raw_content"], per) for pg in good)
            )

            overview = await _build_overview(ctx, name, combined)
            tasks    = await _build_tasks(ctx, name, combined)
            sources  = await _build_sources(ctx, name, pages)
            all_notes.append(_PerformerNotes(name=name, overview=overview, tasks=tasks, sources=sources))

        # Write files under job-scoped vault dir
        folder = vault / _slug(name)
        folder.mkdir(parents=True, exist_ok=True)
        for filename, content in [
            ("overview.md",         overview),
            ("actionable_tasks.md", tasks),
            ("sources.md",          sources),
        ]:
            (folder / filename).write_text(content, encoding="utf-8")

        await ctx.emit("success", f"  {name} → 3 notes written")

    _write_index(vault, field_name, [n.name for n in all_notes])
    md_count = len(list(vault.rglob("*.md")))
    await ctx.emit("success", f"Synthesizer complete — {md_count} notes in {vault}")
