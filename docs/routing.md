# Routing

Sentinel can override the model on a per-request basis and fall back
through an ordered list of candidates if any of them fails.

## Use cases

- **Cost shaping**: route cheap-tier traffic to a cheap model, with
  fallback to the premium model on failure.
- **Provider redundancy**: if OpenAI is having a bad day, transparently
  retry the same request on Anthropic or OpenRouter.
- **Canary**: send 10% of `gpt-4o` traffic to `gpt-4o-mini` and observe
  the verification verdicts (paired with the verification subsystem).

## How it works

1. Every non-streaming `/v1/chat/completions` request runs through the
   routing middleware before being forwarded.
2. The middleware loads all enabled `routing_policies` for the project
   and picks the first one whose `match_jsonpath` matches the request
   body. No match → standard forwarding (Phase 1 behavior).
3. For a matched policy, the middleware rewrites the request `model` to
   the first candidate, stamps `_sentinel.route` provenance, and forwards.
4. If the response status meets a fallback condition (default: HTTP 5xx),
   the middleware advances to the next candidate. Maximum 3 attempts per
   request. Each attempt is its own trace.

## Streaming requests bypass routing

Once we've started streaming bytes to the client, we cannot retry on
another provider — the client has already seen the first chunks. Streaming
falls through to the standard forward path.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/routing-policies` | Create a policy |
| `GET` | `/api/routing-policies?project_id=...` | List |
| `PATCH` | `/api/routing-policies/{id}` | Update |
| `DELETE` | `/api/routing-policies/{id}` | Delete |

## Provenance

The `traces.request_body._sentinel.route` field records:

```json
{
  "policy": "premium-fallback",
  "attempt": 2,
  "original_model": "gpt-4o",
  "parent_request_id": "9b1f...d3a"
}
```

This lets you correlate the chain of attempts in the dashboard.
