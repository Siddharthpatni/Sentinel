"""Playwright + Sentinel example: a browser-using agent whose LLM calls are
all observed by Sentinel.

What this demonstrates
----------------------
1. The agent's loop calls OpenAI through ``sentinel.OpenAI`` — every model
   call is traced, costed, and (if you've set up classifiers) tagged with a
   risk tier.
2. The agent uses Playwright to interact with a real web page, so the
   request bodies contain actual page snippets — useful for verifying that
   PII redaction or risk classifiers are catching what you expect.

Prereqs
-------
    pip install sentinel-sdk playwright openai
    playwright install chromium

    # Point at a running Sentinel gateway (see /examples/hello_openai.py).
    export SENTINEL_URL=http://localhost:8000
    export SENTINEL_API_KEY=sk-sentinel-dev-000

Run
---
    python examples/playwright_agent.py

After the run, open http://localhost:3000 in the dashboard — each
chat-completion call shows up as a trace and (if you've enabled an audit
classifier matching ``$..content``) lands in the audit ledger.
"""

from __future__ import annotations

import os
import sys

from sentinel import OpenAI

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
    """Single chat-completion call — fully traced by Sentinel."""
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

    client = OpenAI(base_url=base_url, api_key=api_key)

    urls = [
        "https://example.com",
        "https://httpbin.org/html",
    ]

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            for url in urls:
                print(f"\n→ visiting {url}")
                page.goto(url, wait_until="domcontentloaded", timeout=15000)
                text = page.inner_text("body")
                summary = summarize_page(client, text)
                print(summary.strip())
        finally:
            browser.close()


if __name__ == "__main__":
    main()
