"""Playwright + Sentinel example: a browser-using agent whose full run is
recorded as a span tree, with each LLM call as a child of the agent span.

What this demonstrates
----------------------
1. ``sentinel.trace(...)`` opens a top-level agent run. Every nested
   ``t.span(...)`` becomes a child node, so the dashboard's waterfall on
   ``/traces/<id>`` shows the whole hierarchy: agent → page fetch →
   summarize (LLM) → ... per URL.
2. The OpenAI calls themselves are still traced by the proxy as
   independent rows in ``/traces`` — useful for cost roll-ups. This
   script's tree captures the *agent* structure on top.

Prereqs
-------
    pip install sentinel-sdk playwright openai
    playwright install chromium

    export SENTINEL_URL=http://localhost:8000
    export SENTINEL_API_KEY=sk-sentinel-dev-000

Run
---
    python examples/playwright_agent.py

After the run, the script prints a trace URL — open it to see the
waterfall.
"""

from __future__ import annotations

import os
import sys

from sentinel import OpenAI, trace

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.stderr.write(
        "Missing dependency: pip install playwright && playwright install chromium\n"
    )
    raise


SYSTEM_PROMPT = """You are a research agent. Given the visible text of a web
page, extract the three most important facts as a short bulleted list. Return
plain text only — no JSON, no markdown headers."""


def summarize_page(client: OpenAI, page_text: str) -> str:
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": page_text[:6000]},
        ],
        temperature=0.2,
    )
    return resp.choices[0].message.content or ""


def main() -> None:
    base_url = os.environ.get("SENTINEL_URL", "http://localhost:8000")
    api_key = os.environ.get("SENTINEL_API_KEY", "sk-sentinel-dev-000")

    client = OpenAI(
        sentinel_url=base_url,
        sentinel_api_key=api_key,
        provider_api_key=os.environ.get("OPENAI_API_KEY"),
    )

    urls = [
        "https://example.com",
        "https://httpbin.org/html",
    ]

    with trace(
        "research_agent",
        sentinel_url=base_url,
        sentinel_api_key=api_key,
    ) as t:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                for url in urls:
                    with t.span("visit_page", span_type="tool", url=url) as fetch_span:
                        print(f"\n→ visiting {url}")
                        page.goto(url, wait_until="domcontentloaded", timeout=15000)
                        text = page.inner_text("body")
                        fetch_span.set_attribute("body_chars", len(text))

                    with t.span("summarize", span_type="llm", model="gpt-4o-mini") as llm_span:
                        summary = summarize_page(client, text)
                        llm_span.set_attribute("summary_chars", len(summary))
                        print(summary.strip())
            finally:
                browser.close()

        print(
            f"\nTrace: {base_url.replace(':8000', ':3000')}/traces/{t.id}"
        )


if __name__ == "__main__":
    main()
