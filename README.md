# Sentinel

**Open-source, self-hostable observability + governance proxy for LLM apps.**

Drop Sentinel in front of any OpenAI / Anthropic call. Get traces, cost
rollups, span-tree waterfalls, replayable datasets, judge-model
verifications, routing fallback, eval suites, an EU-AI-Act-grade audit
ledger, threshold alerts, and a real-time dashboard — all in one
`docker compose up`.

```bash
git clone https://github.com/Siddharthpatni/Sentinel.git
cd Sentinel
export OPENAI_API_KEY=sk-...     # any real OpenAI key (seed costs <$0.01)
make demo                        # boots the stack, seeds 12 traces, opens browser
```

Then open <http://localhost:3000>.

## Why Sentinel

LangSmith / Langfuse / Arize Phoenix are excellent, but each one owns
*one* slice (tracing, evals, observability). Sentinel is the
**single proxy** that does the lot, runs entirely on your own infra, and
the SDK is a two-line drop-in:

```python
from sentinel import OpenAI          # was: from openai import OpenAI
client = OpenAI(
    sentinel_url="http://localhost:8000",
    sentinel_api_key="sk-sentinel-dev-000",
    provider_api_key="sk-...",       # your real OpenAI key
)
# `client.chat.completions.create(...)` works exactly as before.
```

| Capability                  | Sentinel | LangSmith | Langfuse | Phoenix |
| --------------------------- | :------: | :-------: | :------: | :-----: |
| Self-host (single compose)  |    ✓     |     —     |    ✓     |    ✓    |
| Drop-in proxy SDK           |    ✓     |     —     |    —     |    —    |
| Per-call cost + token rollup|    ✓     |     ✓     |    ✓     |    ✓    |
| Span-tree waterfall         |    ✓     |     ✓     |    ✓     |    ✓    |
| LLM-judge verifications     |    ✓     |     —     |    —     |    ✓    |
| Routing + provider fallback |    ✓     |     —     |    —     |    —    |
| Datasets + replay playground|    ✓     |     ✓     |    ✓     |    —    |
| YAML eval suites + CI hook  |    ✓     |     ✓     |    —     |    —    |
| Hash-chained audit log      |    ✓     |     —     |    —     |    —    |
| Threshold alerts            |    ✓     |     ✓     |    —     |    —    |
| BYOK per-project credentials|    ✓     |     —     |    —     |    —    |

## Features

- **Observability** — every call traced with cost, latency, tokens, and
  full request/response bodies. Cost-over-time sparkline on the home
  page. Provider/model/status filters + j/k/↵ keyboard nav on the table.
- **Span trees** — wrap an agent run with `sentinel.trace(...)` and each
  nested `t.span(...)` becomes a child node. The dashboard renders a
  Gantt-style waterfall on `/traces/<id>`.
- **Verifications** — declarative rules re-check primary calls with a
  judge model. Sampled, async, never blocks the caller.
  [docs/verifications.md](docs/verifications.md)
- **Routing & fallback** — per-request model overrides with ordered
  candidate fallback (3 attempts max). Streaming bypasses to preserve
  bytes-on-the-wire semantics. [docs/routing.md](docs/routing.md)
- **Datasets + playground** — capture interesting traces into named
  datasets, replay them from the in-browser playground, save the result
  as expected output. [docs/index.md](docs/index.md)
- **Evals** — YAML-defined suites with 7 assertion types
  (contains/equals/regex/max-latency/max-cost/json-schema/llm-judge), a
  run-history UI, pass-rate trend, and a CI entrypoint for GitHub
  Actions. [docs/evals.md](docs/evals.md)
- **Annotations queue** — `/annotations` lists every trace that doesn't
  yet have human feedback. Open one, thumbs-up/down, add a comment.
- **EU AI Act audit log** — risk-tier classifiers tag inbound calls;
  every tagged call lands in a SHA-256-chained ledger an auditor can
  verify offline. NDJSON export, server-side `/verify`.
  [docs/audit.md](docs/audit.md)
- **Alerts** — threshold checks on cost-per-hour, error-rate, and p95
  latency over rolling windows. On-demand evaluation — wire to cron,
  Slack, or Datadog however you like. [docs/alerts.md](docs/alerts.md)
- **BYOK per-project provider keys** — bring your own
  OpenAI/Anthropic/OpenRouter/Gemini key, encrypted at rest with Fernet
  and never echoed back to the dashboard. One Sentinel instance can
  serve multiple teams without sharing credentials. Live-validate stored
  keys against the provider's model-list endpoint (no token cost).

Learning notes for the concepts behind the implementation live in
[docs/learn/](docs/learn/README.md).

## Quick start

### Option A — one command (recommended)

```bash
git clone https://github.com/Siddharthpatni/Sentinel.git
cd Sentinel
export OPENAI_API_KEY=sk-...
make demo
```

`make demo` boots the docker compose stack, waits for the gateway, runs
[`examples/seed_demo.py`](examples/seed_demo.py) to populate ~12 varied
traces + a span tree + a routing policy + a verification rule + a
dataset, then opens the dashboard in your browser. Total OpenAI cost
under $0.01.

### Option B — bring your own

```bash
docker compose up -d
# Point your existing OpenAI/Anthropic client at http://localhost:8000
```

The dashboard at <http://localhost:3000> shows a quickstart card with
the exact snippet to paste until your first call lands.

## Use Sentinel in your project

```bash
pip install sentinel-sdk
```

**Drop-in proxy:**

```python
from sentinel import OpenAI

client = OpenAI(
    sentinel_url="http://localhost:8000",
    sentinel_api_key="sk-sentinel-dev-000",
    provider_api_key="sk-...",
)
resp = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello!"}],
)
```

**Agent span trees:**

```python
from sentinel import trace

with trace("research_agent",
           sentinel_url="http://localhost:8000",
           sentinel_api_key="sk-sentinel-dev-000") as t:
    with t.span("fetch_page", span_type="tool", url=url):
        ...
    with t.span("summarize", span_type="llm", model="gpt-4o-mini"):
        client.chat.completions.create(...)
# Waterfall at http://localhost:3000/traces/{t.id}
```

**Programmatic control plane** — manage policies, rules, evals from
Python:

```python
from sentinel import Sentinel

s = Sentinel(url="http://localhost:8000", api_key="sk-sentinel-dev-000")
s.routing.create(project_id=..., candidates=[{"model": "gpt-4o-mini"}, ...])
s.verifications.create_rule(project_id=..., judge_model="gpt-4o-mini", ...)
run = s.evals.run(eval_id)
assert run["failed"] == 0          # usable in CI
```

Full API: [sdk/README.md](sdk/README.md) and
[examples/sdk_quickstart.py](examples/sdk_quickstart.py).

## Architecture

```
┌──────────┐    ┌──────────────────┐    ┌──────────────┐
│ Your App │───▶│ Sentinel Gateway │───▶│ OpenAI /     │
│  (SDK)   │◀───│    (FastAPI)     │◀───│ Anthropic    │
└──────────┘    └────────┬─────────┘    └──────────────┘
                         │
                ┌────────▼────────┐
                │  Redis (Celery) │
                └────────┬────────┘
                         │
                ┌────────▼────────┐    ┌──────────────┐
                │ Celery Worker   │───▶│  PostgreSQL  │
                └─────────────────┘    └──────┬───────┘
                                              │
                                     ┌────────▼────────┐
                                     │   Dashboard     │
                                     │   (Next.js)     │
                                     └─────────────────┘
```

| Service     | Port | Description                          |
| ----------- | ---- | ------------------------------------ |
| Gateway     | 8000 | FastAPI proxy + control-plane API    |
| Dashboard   | 3000 | Next.js observability UI             |
| PostgreSQL  | 5432 | Traces, spans, datasets, audit log   |
| Redis       | 6379 | Celery broker (async trace persist)  |
| Worker      | —    | Trace persist, verification judge    |

## Development

```bash
# Gateway
cd gateway
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -v --cov=app
ruff check .

# Dashboard
cd dashboard
npm install
npm run dev
```

Useful Make targets: `make up`, `make down`, `make seed`, `make logs`,
`make test`, `make lint`.

## License

MIT
