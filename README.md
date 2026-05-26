# Sentinel

**Open-source, self-hostable LLM observability proxy.**

Sentinel sits as a drop-in proxy between your application and any LLM provider (OpenAI, Anthropic). It logs every request and response, tracks cost and latency per call, and exposes a live dashboard for inspecting traces.

> 🚧 **Phase 1 MVP** — Under active development.

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
│  Your App   │────▶│ Sentinel Gateway │────▶│ OpenAI /     │
│  (SDK)      │◀────│  (FastAPI)       │◀────│ Anthropic    │
└─────────────┘     └────────┬────────┘     └──────────────┘
                             │
                    ┌────────▼────────┐
                    │  Redis (Celery) │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐     ┌──────────────┐
                    │  Celery Worker  │────▶│  PostgreSQL   │
                    └─────────────────┘     └──────┬───────┘
                                                   │
                                          ┌────────▼────────┐
                                          │   Dashboard     │
                                          │   (Next.js)     │
                                          └─────────────────┘
```

**Services:**
| Service     | Port | Description                        |
|-------------|------|------------------------------------|
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
