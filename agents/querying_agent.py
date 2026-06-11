"""
querying_agent.py
-----------------
Google ADK + Gemini querying agent.

All state flows through JobContext — no module globals, no shared sessions,
no os.environ mutations.

Public API:
    run_querying_agent(ctx: JobContext) -> QueryingOutput
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import requests
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.genai.types import Content, Part
from google.genai import types

from job_context import (
    JobContext,
    GEMINI_MODEL,
    MAX_NAMES,
    MAX_RETRIES,
    QUALITY_THRESHOLD,
)

TAVILY_SEARCH_URL = "https://api.tavily.com/search"


# ── Stateless ADK agent definitions (safe to share — they hold no state) ──
_query_generator = LlmAgent(
    name="query_generator",
    model=GEMINI_MODEL,
    generate_content_config=types.GenerateContentConfig(
        http_options=types.HttpOptions(
            retry_options=types.HttpRetryOptions(
                initial_delay=5,
                attempts=6,
            )
        )
    ),
    instruction=(
        "You are a search-query expert. Given a task description, generate a precise "
        "web-search query (≤12 words). Return ONLY the query string — no explanation, "
        "no quotes, no markdown."
    ),
)

_evaluator = LlmAgent(
    name="evaluator",
    model=GEMINI_MODEL,
    generate_content_config=types.GenerateContentConfig(
        http_options=types.HttpOptions(
            retry_options=types.HttpRetryOptions(
                initial_delay=5,
                attempts=6,
            )
        )
    ),
    instruction=(
        "You are a search-quality evaluator. Score the query result quality on 0.0-1.0:\n"
        "  1.0 = specific real names / URLs, highly relevant.\n"
        "  0.0 = empty, off-topic, or too generic.\n"
        "Respond ONLY with valid JSON (no markdown):\n"
        '{"score": <float>, "reason": "<brief>", "feedback": "<improvement hint>"}'
    ),
)

_names_extractor = LlmAgent(
    name="names_extractor",
    model=GEMINI_MODEL,
    generate_content_config=types.GenerateContentConfig(
        http_options=types.HttpOptions(
            retry_options=types.HttpRetryOptions(
                initial_delay=5,
                attempts=6,
            )
        )
    ),
    instruction=(
        f"Extract person names from search result text. "
        f"Return ONLY a JSON array of up to {MAX_NAMES} name strings. "
        "No markdown, no extra text."
    ),
)


# ── Per-invocation ADK runner helper ──────────────────────────────────────
async def _run_agent(ctx: JobContext, agent: LlmAgent, prompt: str) -> str:
    """
    Each call creates a fresh session scoped to this job's session_service.
    session_service is per-JobContext, so sessions never collide across jobs.
    user_id is scoped to job_id to prevent any cross-job contamination.
    """
    runner  = Runner(
        agent=agent,
        app_name=f"{agent.name}.{ctx.job_id}",   # unique app name per job
        session_service=ctx.session_service,       # job-isolated service
    )
    session = await ctx.session_service.create_session(
        app_name=f"{agent.name}.{ctx.job_id}",
        user_id=ctx.job_id,                        # scoped to this job
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


# ── Tavily (pure I/O, no state) ────────────────────────────────────────────
def _tavily_search(api_key: str, query: str, max_results: int = 7) -> list[dict]:
    resp = requests.post(
        TAVILY_SEARCH_URL,
        json={
            "api_key": api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "advanced",
            "include_answer": True,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("results", [])


# ── Agent steps ────────────────────────────────────────────────────────────
async def _generate_query(ctx: JobContext, task_description: str) -> str:
    return await _run_agent(ctx, _query_generator, task_description)


async def _evaluate_results(
    ctx: JobContext, query: str, results: list[dict]
) -> tuple[float, str, str]:
    sample = json.dumps(results[:3], ensure_ascii=False, indent=2)
    raw    = await _run_agent(ctx, _evaluator, f"Query: {query}\n\nTop-3 results:\n{sample}")
    raw    = raw.strip().lstrip("```json").rstrip("```").strip()
    try:
        data = json.loads(raw)
        return float(data.get("score", 0.0)), data.get("reason", ""), data.get("feedback", "")
    except Exception:
        return 0.0, "parse error", ""


async def _extract_names(ctx: JobContext, results: list[dict]) -> list[str]:
    combined = "\n".join(
        f"Title: {r.get('title','')}\n{r.get('content','')}" for r in results
    )
    prompt = f"Field: {ctx.field_name}\n\nSearch results:\n{combined[:6000]}"
    raw    = await _run_agent(ctx, _names_extractor, prompt)
    raw    = raw.strip().lstrip("```json").rstrip("```").strip()
    try:
        names = json.loads(raw)
        return [n for n in names if isinstance(n, str)][:MAX_NAMES]
    except Exception:
        return []


async def _run_with_retry(
    ctx: JobContext,
    tavily_api_key: str,
    task_fn,
    span_name: str,
) -> tuple[str, list[dict], float]:
    """
    Generate query → search → evaluate → retry up to MAX_RETRIES.
    Tracing uses ctx.tracer, which is isolated to this job's Phoenix project.
    """
    feedback = ""
    query    = ""
    results: list[dict] = []
    score    = 0.0

    with ctx.tracer.start_as_current_span(span_name) as span:
        span.set_attribute("job_id", ctx.job_id)
        span.set_attribute("field",  ctx.field_name)

        for attempt in range(1, MAX_RETRIES + 2):
            task_desc = await task_fn(feedback)
            query     = await _generate_query(ctx, task_desc)

            span.set_attribute(f"attempt_{attempt}_query", query)
            await ctx.emit("info", f"[{span_name}] attempt={attempt} query={query!r}")

            results = _tavily_search(tavily_api_key, query)
            score, reason, feedback = await _evaluate_results(ctx, query, results)

            span.set_attribute(f"attempt_{attempt}_score", score)
            await ctx.emit("info", f"[{span_name}] score={score:.2f} — {reason}")

            if score >= QUALITY_THRESHOLD or attempt > MAX_RETRIES:
                break

        span.set_attribute("final_score",       score)
        span.set_attribute("passed_threshold",  score >= QUALITY_THRESHOLD)

    return query, results, score


# ── Data models ────────────────────────────────────────────────────────────
@dataclass
class PerformerResult:
    name: str
    strategy_urls: list[str] = field(default_factory=list)


@dataclass
class QueryingOutput:
    field: str
    performers: list[PerformerResult] = field(default_factory=list)


# ── Public entry point ─────────────────────────────────────────────────────
async def run_querying_agent(ctx: JobContext, tavily_api_key: str) -> QueryingOutput:
    """
    Fully isolated — all state comes from ctx, all secrets passed explicitly.
    Safe to call concurrently for different jobs.
    """
    output = QueryingOutput(field=ctx.field_name)

    await ctx.emit("info", f"Querying Agent started | field={ctx.field_name!r}")

    # Step 1: discover names
    async def names_task(fb: str) -> str:
        fb_block = f" Previous feedback: {fb}" if fb else ""
        return (
            f"Generate a web-search query to find the top {MAX_NAMES} most successful "
            f"individuals in the field of: {ctx.field_name}. "
            f"Results must list real people's names.{fb_block}"
        )

    _, name_results, _ = await _run_with_retry(
        ctx, tavily_api_key, names_task, "names-discovery"
    )
    names = await _extract_names(ctx, name_results)
    await ctx.emit("success", f"Discovered {len(names)} performers: {', '.join(names)}")

    # Step 2: strategy URLs per performer
    for name in names:
        async def strategy_task(fb: str, _name: str = name) -> str:
            fb_block = f" Previous feedback: {fb}" if fb else ""
            return (
                f"Generate a web-search query to find articles or interviews explaining "
                f"the specific strategies used by {_name} to become a top performer in "
                f"{ctx.field_name}. Focus on actionable strategies.{fb_block}"
            )

        _, strat_results, score = await _run_with_retry(
            ctx, tavily_api_key, strategy_task,
            f"strategy-{name.replace(' ', '_')}"
        )
        urls = [r["url"] for r in strat_results if r.get("url")]
        await ctx.emit("info", f"  {name} → {len(urls)} URLs (score={score:.2f})")
        output.performers.append(PerformerResult(name=name, strategy_urls=urls))

    # Persist to job-scoped path
    # with open(ctx.querying_path, "w") as f:
    #     json.dump(
    #         {
    #             "field": output.field,
    #             "performers": [
    #                 {"name": p.name, "strategy_urls": p.strategy_urls}
    #                 for p in output.performers
    #             ],
    #         },
    #         f,
    #         indent=2,
    #     )

    ctx.write_file(JobContext.QUERYING_FILE, json.dumps(  {
                "field": output.field,
                "performers": [
                    {"name": p.name, "strategy_urls": p.strategy_urls}
                    for p in output.performers
                ],
            }, indent=2))


    await ctx.emit("success", f"Querying Agent complete →  {ctx.QUERYING_FILE}")
    return output
