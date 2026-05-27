# Sentinel docs

A local-first, open-source LLM observability proxy. Drop in front of OpenAI
or Anthropic; get traces, costs, judge verifications, routing, evals, audit
logs, and alerts — without sending your traffic to a SaaS.

## Start here

| If you want to... | Read |
| --- | --- |
| Get the gateway running and see your first trace | [`/README.md`](../README.md) (root) |
| Use Sentinel from another project (Python module) | [`/sdk/README.md`](../sdk/README.md) |

## Module guides

| Module | Doc | One-liner |
| --- | --- | --- |
| Verifications | [verifications.md](./verifications.md) | LLM-as-judge re-check, JSONPath match + sampling. |
| Routing | [routing.md](./routing.md) | Multi-candidate, fallback on 5xx / token thresholds. |
| Evals | [evals.md](./evals.md) | YAML suites, run history, CI gate. |
| Audit | [audit.md](./audit.md) | EU AI Act risk tiers + tamper-evident ledger. |
| Alerts | [alerts.md](./alerts.md) | Cost / error-rate / p95-latency thresholds. |

## Concept notes

The [`/docs/learn/`](./learn/) folder collects short, opinionated notes on
the libraries and patterns Sentinel leans on (FastAPI lifespans, Celery
include-list, JSONPath limits, hash-chained ledgers, etc.). Read them when
you're touching the relevant area.

## Examples

The [`/examples/`](../examples/) folder has runnable scripts:

- `hello_openai.py` / `hello_anthropic.py` — the 5-line "does it work?" test
- `sdk_quickstart.py` — control-plane (create rules, run evals, fetch traces)
- `playwright_agent.py` — a browser agent whose LLM calls are all observed
- `eval_suite_example.yaml`, `routing_policy_example.json` — pasteable configs

## API surface

The gateway speaks two kinds of HTTP:

**Data plane** — OpenAI/Anthropic-compatible. Point any SDK at
`http://localhost:8000` and use it as you normally would.

**Control plane** — REST under `/api/...`:

```
/api/projects                    list projects
/api/traces                      list / get / stats / timeseries
/api/verification-rules          CRUD
/api/verifications               list judge results
/api/routing-policies            CRUD
/api/evals                       CRUD + /run + /runs + /trends
/api/audit/classifiers           CRUD
/api/audit/export                NDJSON ledger stream
/api/audit/verify                chain integrity check
/api/alerts                      CRUD + /check
```

Every endpoint is documented in the corresponding module guide above.
