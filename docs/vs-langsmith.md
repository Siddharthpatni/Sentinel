# Sentinel vs LangSmith

A side-by-side look at what Sentinel offers compared to LangSmith, and where
the two projects intentionally diverge.

> **TL;DR** — Sentinel is a self-hostable, OpenAI/Anthropic-compatible proxy
> with first-class **EU AI Act audit logging**, **policy-based routing**,
> **judge-based verifications**, **threshold alerts**, and **annotations +
> conversation threads**. LangSmith is a hosted observability + evals product
> tightly coupled to LangChain. If you need a drop-in proxy you can run inside
> your own VPC and that produces a tamper-evident compliance ledger,
> Sentinel is the answer.

## Feature parity matrix

| Capability                          | LangSmith | Sentinel |
| ----------------------------------- | :-------: | :------: |
| Trace capture (req/resp/cost/latency) |    ✓     |    ✓    |
| Search / filter traces              |    ✓     |    ✓    |
| Trace timeseries + sparklines       |    ✓     |    ✓    |
| Human feedback (👍/👎 + comments)   |    ✓     |    ✓    |
| Conversation threads / sessions     |    ✓     |    ✓    |
| Dataset-style eval suites           |    ✓     |    ✓    |
| LLM-as-judge verifications          |    ✓     |    ✓    |
| Pass-rate trend over time           |    ✓     |    ✓    |
| Threshold alerts (cost / errors / p95) |    ✓     |    ✓    |
| Drop-in OpenAI / Anthropic SDK proxy |   partial  |   ✓ (URL swap only)   |
| Policy-based **routing / fallback** at proxy |   ✗     |    ✓    |
| **EU AI Act** risk-tier classifiers + audit ledger |    ✗     |    ✓    |
| Tamper-evident SHA-256 hash chain   |    ✗     |    ✓    |
| Self-hostable (Docker Compose)      |   limited (enterprise)   |    ✓ (default)    |
| Prompt registry / playground        |    ✓     |    ✗ (out of scope) |
| LangChain-native callbacks          |    ✓     |    ✗ (proxy is framework-agnostic) |

## What Sentinel matches

- **Tracing UI** — request/response JSON viewer, token counts, cost, latency,
  per-provider/per-model filters, status-code badges.
- **Human feedback** — `/api/annotations` with thumbs up / down / neutral,
  freeform dimensions (`overall`, `accuracy`, ...), comments, author.
  Surfaced as a panel on each trace detail page.
- **Sessions / threads** — pass
  `extra_body={"_sentinel": {"session_id": "user-123"}}` on a chat completion
  and Sentinel groups the trace into a session row. Browse at `/sessions`.
- **Evals** — YAML eval suites with deterministic checks + LLM judges,
  triggered locally or via CI (`sentinel.evals.run(eval_id)`), with
  pass-rate trend charts.
- **Alerts** — threshold rules on `cost_per_hour_usd`, `error_rate_pct`,
  `latency_p95_ms` over a rolling window.

## Where Sentinel goes further

### EU AI Act compliance (unique)
A risk-tier classifier engine (`/api/audit/classifiers`) labels every
inference with `prohibited | high | limited | minimal`, persists it to an
append-only audit ledger, and chains entries with a SHA-256 hash so any
tampering is detectable. Export the full ledger as NDJSON for regulators or
internal review.

### Routing as a first-class primitive
Sentinel is a **proxy**, not just an SDK callback. Routing policies match
requests by JSONPath and steer them to a preferred model, with automatic
fallback on `http_5xx`, `429`, or latency budgets. No code change in the
client app — flip a policy in the dashboard and the next request honors it.

### Self-hostable by default
`docker compose up` and you have postgres + redis + gateway + worker +
dashboard, all in your VPC. No data ever leaves your infrastructure.

## Where Sentinel intentionally does *not* compete

- **Prompt registry + playground** — LangSmith ships a "Prompt Hub" and an
  interactive playground. Sentinel does not, by design: prompts belong in
  source control next to the code that uses them. We're not interested in
  becoming another `git` for prompts.
- **LangChain-native callbacks** — Sentinel is framework-agnostic. We
  intercept at the wire (OpenAI/Anthropic-compatible HTTP) rather than at
  the LangChain runtime. The trade-off: you don't get free chain-step
  visibility, but you also don't need LangChain at all.

## Picking between them

| If you need...                                          | Pick      |
| ------------------------------------------------------- | --------- |
| Hosted SaaS with zero ops, deep LangChain integration   | LangSmith |
| Self-host inside your own VPC                           | Sentinel  |
| EU AI Act compliance / tamper-evident logs              | Sentinel  |
| Drop-in proxy that works without changing SDK code      | Sentinel  |
| Policy-based routing + fallback at the gateway          | Sentinel  |
| Prompt registry + playground                            | LangSmith |
