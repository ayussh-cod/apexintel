"""
tavily_extractor.py
-------------------
Stateless Tavily URL extractor.

All I/O paths come from ctx.workspace — no fixed filenames, no globals.

Public API:
    run_extractor(ctx: JobContext, tavily_api_key: str) -> list[PerformerExtraction]
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Optional

import requests

from job_context import JobContext

TAVILY_EXTRACT_URL = "https://api.tavily.com/extract"
BATCH_SIZE         = 5
REQUEST_DELAY_SEC  = 1.0


@dataclass
class ExtractedPage:
    url: str
    raw_content: str
    failed: bool = False
    error: Optional[str] = None


@dataclass
class PerformerExtraction:
    name: str
    pages: list[ExtractedPage] = field(default_factory=list)


def _extract_batch(api_key: str, urls: list[str]) -> list[dict]:
    resp = requests.post(
        TAVILY_EXTRACT_URL,
        json={"api_key": api_key, "urls": urls},
        timeout=60,
    )
    resp.raise_for_status()
    data   = resp.json()
    failed = set(data.get("failed_urls", []))

    out = [
        {
            "url":         r.get("url", ""),
            "raw_content": r.get("raw_content", ""),
            "failed":      False,
            "error":       None,
        }
        for r in data.get("results", [])
    ]
    for url in failed:
        out.append({"url": url, "raw_content": "", "failed": True,
                    "error": "Tavily extraction failed"})
    return out


async def run_extractor(ctx: JobContext, tavily_api_key: str) -> list[PerformerExtraction]:
    """
    Reads ctx.querying_path, extracts all URLs, writes to ctx.extracted_path.
    All paths are job-scoped; safe for concurrent execution.
    """
    with open(ctx.querying_path) as f:
        data = json.load(f)

    performers = data["performers"]
    extractions: list[PerformerExtraction] = []

    await ctx.emit("info", f"Extractor started — {len(performers)} performers")

    for p in performers:
        name         = p["name"]
        urls         = list(dict.fromkeys(p["strategy_urls"]))[:20]
        extraction   = PerformerExtraction(name=name)

        if not urls:
            await ctx.emit("info", f"  {name}: no URLs, skipping")
            extractions.append(extraction)
            continue

        await ctx.emit("info", f"  Extracting {len(urls)} URLs for {name}")

        for i in range(0, len(urls), BATCH_SIZE):
            batch = urls[i : i + BATCH_SIZE]
            try:
                results = _extract_batch(tavily_api_key, batch)
            except requests.HTTPError as exc:
                await ctx.emit("error", f"  Batch failed for {name}: {exc}")
                for url in batch:
                    extraction.pages.append(
                        ExtractedPage(url=url, raw_content="", failed=True, error=str(exc))
                    )
                continue

            for r in results:
                extraction.pages.append(
                    ExtractedPage(
                        url=r["url"],
                        raw_content=r["raw_content"],
                        failed=r["failed"],
                        error=r.get("error"),
                    )
                )

            if i + BATCH_SIZE < len(urls):
                time.sleep(REQUEST_DELAY_SEC)

        ok  = sum(1 for pg in extraction.pages if not pg.failed)
        bad = sum(1 for pg in extraction.pages if pg.failed)
        await ctx.emit("success", f"  {name}: {ok} extracted, {bad} failed")
        extractions.append(extraction)

    # Persist to job-scoped path
    with open(ctx.extracted_path, "w") as f:
        json.dump(
            {
                "field": data["field"],
                "performers": [
                    {
                        "name": e.name,
                        "pages": [
                            {
                                "url":         pg.url,
                                "raw_content": pg.raw_content,
                                "failed":      pg.failed,
                                "error":       pg.error,
                            }
                            for pg in e.pages
                        ],
                    }
                    for e in extractions
                ],
            },
            f,
            indent=2,
        )

    await ctx.emit("success", f"Extractor complete → {ctx.extracted_path}")
    return extractions
