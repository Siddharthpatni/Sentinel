# Sentinel

**Open-source, self-hostable LLM observability proxy.**

Sentinel sits as a drop-in proxy between your application and any LLM provider (OpenAI, Anthropic). It logs every request and response, tracks cost and latency per call, and exposes a live dashboard for inspecting traces.

> **Phase 3** — observability · verification · routing · evals · audit · alerts.

## Features

- **Observability** — every LLM call traced with cost, latency, tokens,
  and full request/response bodies in a live dashboard. Cost over the
  last 24h shown as an inline sparkline.
- **Verifications** — declarative rules re-check primary calls with a
  judge model. Sampled, async, never blocks the caller. See
  [docs/verifications.md](docs/verifications.md).
- **Routing & fallback** — per-request model overrides with ordered
  candidate fallback (3 attempts max). Streaming bypasses to preserve
  bytes-on-the-wire semantics. See [docs/routing.md](docs/routing.md).
- **Evals** — YAML-defined regression suites with seven assertion types
  (contains/equals/regex/max-latency/max-cost/json-schema/llm-judge), a
  run-history UI, pass-rate trend endpoint, and a CI entrypoint for
  GitHub Actions. See [docs/evals.md](docs/evals.md).
- **EU AI Act audit log** — risk-tier classifiers tag inbound calls;
  every tagged call lands in a SHA-256-chained ledger an auditor can
  verify offline. NDJSON export, server-side `/verify`. See
  [docs/audit.md](docs/audit.md).
- **Alerts** — threshold checks on cost-per-hour, error-rate, and p95
  latency over rolling windows. On-demand evaluation — wire to cron,
  Slack, or Datadog however you like. See [docs/alerts.md](docs/alerts.md).
- **BYOK — per-project provider keys** — bring your own OpenAI /
  Anthropic / OpenRouter / Gemini key, encrypted at rest with Fernet
  and never echoed back to the dashboard after creation. Per-project
  scoping means one Sentinel instance can serve multiple teams without
  sharing credentials. Manage at
  [/settings/keys](http://localhost:3000/settings/keys) or via
  `POST /api/credentials`. Live-validate stored keys against the
  provider's model-list endpoint (no token cost) with
  `POST /api/credentials/{id}/test`. Background: see
  [docs/learn/symmetric-encryption-fernet.md](docs/learn/symmetric-encryption-fernet.md).

Learning notes for the concepts behind the implementation live in
[docs/learn/](docs/learn/README.md).

## Use Sentinel in your project

Sentinel ships as an installable Python module. Drop it into any existing
project to get observability + verifications + routing + evals on every
LLM call.

```bash
pip install sentinel-sdk   # or: pip install -e ./sdk from a checkout
```

**1. Drop-in proxy** — swap two lines, keep the rest of your code:

```python
from sentinel import OpenAI

client = OpenAI(
    sentinel_api_key="sk-sentinel-dev-000",
    sentinel_url="http://localhost:8000",
    provider_api_key="sk-...",   # your real OpenAI key
)
# Use client.chat.completions.create(...) exactly as before.
```

**2. Programmatic control plane** — manage rules, policies, and evals
from Python instead of the dashboard:

```python
from sentinel import Sentinel

s = Sentinel(url="http://localhost:8000", api_key="sk-sentinel-dev-000")
s.verifications.create_rule(project_id=..., name=..., match_jsonpath=..., ...)
s.routing.create(project_id=..., candidates=[{"model": "gpt-4o-mini"}, ...])
run = s.evals.run(eval_id)                # block-and-return: usable in CI
assert run["failed"] == 0
```

Full API and more examples in [sdk/README.md](sdk/README.md) and
[examples/sdk_quickstart.py](examples/sdk_quickstart.py).

## Quick Start

```bash
git clone https://github.com/Siddharthpatni/Sentinel.git
cd Sentinel
cp .env.example .env          # Fill in your OPENAI_API_KEY / ANTHROPIC_API_KEY
docker compose up -d
# Open http://localhost:3000 — traces appear in real time
```

## How It Works

1. **Swap your base URL** — Point your OpenAI/Anthropic SDK at `http://localhost:8000`
2. **Make API calls as usual** — Sentinel transparently proxies to the upstream provider
3. **See everything** — Every call appears in the live dashboard with cost, latency, tokens, and full request/response bodies

## Using the SDK

The SDK provides drop-in replacement clients:

```python
from sentinel import OpenAI

client = OpenAI(
    sentinel_api_key="sk-sentinel-dev-000",
    sentinel_url="http://localhost:8000",
)

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello!"}],
)
print(response.choices[0].message.content)
```

Or with Anthropic:

```python
from sentinel import Anthropic

client = Anthropic(
    sentinel_api_key="sk-sentinel-dev-000",
    sentinel_url="http://localhost:8000",
    provider_api_key="sk-ant-...",
)

response = client.messages.create(
    model="claude-3-5-haiku-20241022",
    max_tokens=100,
    messages=[{"role": "user", "content": "Hello!"}],
)
```

## Architecture

```
┌─────────────┐     ┌─────────────────┐     ┌──────────────┐
│  Your App   │────▶│ Sentinel Gateway│────▶│ OpenAI /     │
│  (SDK)      │◀────│  (FastAPI)      │◀────│ Anthropic    │
└─────────────┘     └────────┬────────┘     └──────────────┘
                             │
                    ┌────────▼────────┐
                    │  Redis (Celery) │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐     ┌──────────────┐
                    │  Celery Worker  │────▶│  PostgreSQL  │
                    └─────────────────┘     └──────┬───────┘
                                                   │
                                          ┌────────▼────────┐
                                          │   Dashboard     │
                                          │   (Next.js)     │
                                          └─────────────────┘
```

**Services:**
| Service     | Port | Description                         |
|-------------|------|------------------------------------ |
| Gateway     | 8000 | FastAPI proxy + API                 |
| Dashboard   | 3000 | Next.js observability UI            |
| PostgreSQL  | 5432 | Trace storage                       |
| Redis       | 6379 | Celery task broker                  |
| Worker      | —    | Celery background trace persistence |

## Development

### Gateway (Python)

```bash
cd gateway
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -v --cov=app
ruff check .
```

### Dashboard (TypeScript)

```bash
cd dashboard
npm install
npm run dev
```

### Running Tests

```bash
# Backend
cd gateway && pytest tests/ -v --cov=app --cov-report=term-missing

# Frontend
cd dashboard && npx tsc --noEmit

# Linting
ruff check gateway/ sdk/
```

## License

MIT
