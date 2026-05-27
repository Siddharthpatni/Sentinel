# Verifications

Sentinel can re-check any primary LLM call with a *judge model* and store
a verdict alongside the original trace. This is how you catch regressions
that don't surface as HTTP errors — wrong answers, hallucinated citations,
off-tone responses.

## How it works

1. The gateway records every chat completion as a `traces` row.
2. After the trace commits, Celery enqueues `evaluate_trace` for that row.
3. The orchestrator loads all enabled `verification_rules` for the trace's
   project. Each rule has:
   - A JSONPath to match the request body (e.g. `$.messages[?(@.role ==
     "user")]` runs against every user-turn call).
   - A sample rate (0.0–1.0).
   - A judge model and prompt template.
4. For each matching, sampled rule, the orchestrator renders the template
   in a Jinja2 sandbox, calls the judge through the gateway (so the judge
   call is itself traced), parses the JSON verdict, and writes a
   `verifications` row.

## Anti-recursion

Judge calls carry `X-Sentinel-Judge: 1` and `_sentinel.is_judge: true` in
the body. The orchestrator skips any trace with that marker — without it,
the judge of a judge of a judge would loop forever.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/verification-rules?project_id=...` | List rules |
| `POST` | `/api/verification-rules` | Create a rule |
| `PATCH` | `/api/verification-rules/{id}` | Update (toggle, edit prompt) |
| `DELETE` | `/api/verification-rules/{id}` | Delete |
| `GET` | `/api/verifications?trace_id=...&verdict=...` | List verdicts |

## Failure mode

Verification failure is never bubbled to the primary caller. If the judge
model 500s, we record a `verdict="error"` row and move on. Sentinel
prioritises not breaking your application over verifying every call.
