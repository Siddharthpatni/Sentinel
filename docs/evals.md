# Evals

Sentinel evals are YAML-defined regression suites. Each suite is a list of
test cases against a model, with assertions on the response, latency, or
cost. Suites can be triggered from the dashboard or from a GitHub Action.

## Suite shape

```yaml
name: customer-support-quality
target:
  endpoint: /v1/chat/completions
  model: gpt-4o-mini
cases:
  - name: refund-tone
    input:
      messages:
        - role: user
          content: I want a refund for order #1234.
    assertions:
      - type: contains
        path: $.choices[0].message.content
        value: refund
        case_sensitive: false
      - type: max_latency_ms
        value: 5000
      - type: max_cost_usd
        value: 0.01
```

## Assertion types

| Type | Fields | What passes |
| --- | --- | --- |
| `contains` / `not_contains` | `path`, `value`, `case_sensitive` | substring (or its absence) at the JSONPath |
| `equals` / `not_equals` | `path`, `value` | strict equality |
| `regex` | `path`, `pattern` | `re.search` matches |
| `max_latency_ms` | `value` | call latency ≤ value |
| `max_cost_usd` | `value` | cost ≤ value |
| `json_schema` | `schema` | response validates against schema |
| `llm_judge` | `judge_model`, `criterion`, `passing_confidence` | judge returns agree with confidence ≥ threshold |

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/evals` | Create or upsert a suite (by name) |
| `GET` | `/api/evals?project_id=...` | List suites |
| `DELETE` | `/api/evals/{id}` | Delete |
| `POST` | `/api/evals/{id}/run` | Trigger a run |
| `GET` | `/api/evals/{id}/runs` | List runs |
| `GET` | `/api/evals/{id}/runs/{run_id}` | Run detail + per-case logs |

## CI integration

`python -m app.evals.github_action --suite path/to/suite.yaml --gateway-url
https://sentinel.example --api-key $SENTINEL_API_KEY --fail-on-regression`

The action posts a markdown summary to `$GITHUB_STEP_SUMMARY` and exits
non-zero on any failure when `--fail-on-regression` is set. See
`.github/workflows/eval.yml` for a wiring template.
