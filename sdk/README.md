# sentinel-sdk

Python SDK for [Sentinel](https://github.com/Siddharthpatni/Sentinel) — the
open-source LLM observability proxy. Drop into any project, swap two lines,
get traces, verifications, routing, and evals on every LLM call.

## Install

```bash
pip install sentinel-sdk
```

(Or, until published, install from the repo: `pip install -e
./sdk` from a Sentinel checkout.)

## Two ways to use it

### 1. Drop-in LLM proxy (data plane)

`sentinel.OpenAI` and `sentinel.Anthropic` are subclasses of the official
clients. Same surface area, but every call routes through your Sentinel
gateway and gets traced.

```python
from sentinel import OpenAI

client = OpenAI(
    sentinel_api_key="sk-sentinel-dev-000",
    sentinel_url="http://localhost:8000",
    provider_api_key="sk-...",  # your real OpenAI key, forwarded upstream
)

resp = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello!"}],
)
```

That's the whole change. No code rewrites, no decorators, no middleware to
register. If you have an existing project, this is two lines.

Same for Anthropic:

```python
from sentinel import Anthropic
client = Anthropic(sentinel_api_key=..., sentinel_url=..., provider_api_key=...)
```

### 2. Programmatic control plane

`sentinel.Sentinel` is a typed client for the gateway's REST API. Use it
to manage verification rules, routing policies, eval suites, and to fetch
traces — without hand-rolling HTTP.

```python
from sentinel import Sentinel

s = Sentinel(url="http://localhost:8000", api_key="sk-sentinel-dev-000")

# Observability
traces = s.traces.list(limit=20)
stats = s.traces.stats()

# Verifications: auto re-check every user turn with a judge model.
s.verifications.create_rule(
    project_id=project_id,
    name="quality-check",
    match_jsonpath='$.messages[?(@.role == "user")]',
    sample_rate=0.1,
    judge_model="gpt-4o-mini",
    judge_prompt_template="...",
)

# Routing: cheap model first, fall back to premium on 5xx.
s.routing.create(
    project_id=project_id,
    name="cost-shaping",
    match_jsonpath="$.model[?(@ == 'gpt-4o')]",
    candidates=[{"model": "gpt-4o-mini"}, {"model": "gpt-4o"}],
)

# Evals: YAML-defined regression suites, runnable from code or CI.
suite = s.evals.create(project_id=project_id, yaml_source=open("suite.yaml").read())
run = s.evals.run(suite["id"], triggered_by="ci", git_sha="abc123")
print(f"{run['passed']}/{run['total']} passed")
```

## Why drop this into your project

- **Free observability** in 2 lines — costs, latency, tokens, full bodies.
- **CI gate** for LLM quality regressions via `sentinel.evals.run()`.
- **Cost control** via routing policies — no code changes when you want
  to swap providers.
- **Verifications** that flag bad outputs in the background without
  blocking the request.

## API reference

| Resource | Methods |
| --- | --- |
| `s.projects` | `list()` |
| `s.traces` | `list()`, `get(id)`, `stats()` |
| `s.verifications` | `list_rules()`, `create_rule()`, `update_rule()`, `delete_rule()`, `list()` |
| `s.routing` | `list()`, `create()`, `update()`, `delete()` |
| `s.evals` | `list()`, `create()`, `delete()`, `run()`, `runs()`, `run_detail()` |

All methods return plain `dict` / `list[dict]` shaped exactly like the
gateway's JSON responses. Errors raise `SentinelError(status_code, body)`.

## Context manager

```python
with Sentinel(url=...) as s:
    s.evals.run(eval_id)
# httpx client closed automatically
```

## License

MIT. Issues and PRs welcome at
[github.com/Siddharthpatni/Sentinel](https://github.com/Siddharthpatni/Sentinel).
