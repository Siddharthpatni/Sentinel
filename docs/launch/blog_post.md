# Sentinel — launch blog post (LinkedIn / Medium draft)

**Suggested title:** *I built an open-source LLM observability proxy that
runs on my laptop — here's why I stopped paying for SaaS.*

**Suggested subtitle:** *Traces, evals, EU AI Act audit logs, and threshold
alerting in one self-hosted gateway. Drop it in front of OpenAI or
Anthropic; no SDK changes.*

---

For the last 90 days I've been building **Sentinel**, an open-source proxy
that sits between your application and your LLM provider and logs every
call. It's now feature-complete enough that I run it on every project I
ship.

Here's what it does, why I built it, and how it's different from the SaaS
observability tools you've probably already evaluated.

## The problem

LLM workloads have an observability gap. The tooling that exists today
mostly falls into three buckets:

1. **Provider dashboards** (OpenAI, Anthropic) — useful for billing, useless
   for debugging a specific user's bad answer.
2. **SaaS observability** (LangSmith, Helicone, Arize, etc.) — solid
   products, but they want your prompts and responses on their servers,
   and the EU AI Act + every enterprise compliance review pushes back on
   that.
3. **Roll-your-own logging** — what most teams end up doing, badly. You
   log to Postgres, lose token counts on streams, never get around to
   costs, and the eval setup never happens.

Sentinel is the bucket I wanted but couldn't find: **self-hosted, OpenAI-
and Anthropic-compatible, with first-class compliance primitives**.

## How it works

Sentinel is a FastAPI gateway. Point any OpenAI or Anthropic SDK at it
instead of `api.openai.com` and you're done:

```python
from sentinel import OpenAI

client = OpenAI(
    base_url="http://localhost:8000",
    api_key="sk-sentinel-dev-000",
)

# everything else is just the OpenAI SDK
client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "hi"}],
)
```

Behind that one URL change, you get:

- **Trace logging** — every request + response in Postgres, with token
  counts and computed cost
- **LLM-as-judge verifications** — JSONPath-matched, sample-rate-throttled
  re-checks with a configurable judge model
- **Routing** — multi-candidate policies with fallback on 5xx
- **Eval suites** — YAML test cases with a CI integration that fails the
  PR on regressions
- **EU AI Act audit log** — risk-tier classifiers + a SHA-256 chained
  ledger that an external auditor can verify offline
- **Threshold alerts** — cost/hour, error-rate, p95 latency over rolling
  windows
- **A Next.js dashboard** — traces, charts, classifier/alert management

## What I learned

A few things that surprised me along the way.

**1. The compliance bit is the moat.** Most observability tools added EU
AI Act features as an afterthought. Doing it right means a separate
append-only ledger with a hash chain, classifiers that run at ingest, and
an export endpoint that streams NDJSON for auditors. None of that is hard
— but it has to be designed in, and it changes the data model.

**2. Streaming is the hard part.** Buffering streamed tokens to compute
cost and capture the full response, while still streaming bytes to the
client, is where most "we'll add observability later" projects die. I cap
the buffer at a few MB and drop the capture if a stream is enormous.

**3. JSONPath + Jinja was the right power-to-complexity ratio.** I tried
a few prompt-templating DSLs. JSONPath for matching + Jinja's sandboxed
environment for templates ended up being the sweet spot. Users write
patterns like `$.messages[?(@.role == "user")]` and prompts like
`{{ response.choices[0].message.content }}`.

**4. On-demand alerting is enough.** I almost built a background
scheduler. Then I realized that hitting `POST /api/alerts/{id}/check` from
a cron or a Slack synthetic check is one line of YAML and zero new
dependencies. Half the work for 90% of the value.

## What's next

The code is at **github.com/Siddharthpatni/Sentinel**. The dashboard is at
`localhost:3000` after `docker compose up`. The Python SDK is `pip install
sentinel-sdk`.

I'd love feedback on:

- The control-plane API shape — too REST-y? Should it be GraphQL?
- The risk-tier classifier model — does it fit your team's actual AI Act
  workflow?
- The eval YAML — is it expressive enough?

If you've shipped LLM features in production and bounced off the same
observability gap, I'd love to hear what you ended up using instead.

— *Siddharth Patni*

---

**Posting checklist**

- [ ] Add a hero screenshot (the traces dashboard with cost sparkline)
- [ ] Add a second screenshot (the audit page with classifiers + verify result)
- [ ] Confirm the GitHub repo is public
- [ ] Confirm the SDK is published to PyPI (or call it "PyPI coming soon")
- [ ] Pin the post on LinkedIn for 7 days
- [ ] Cross-post to /r/LocalLLaMA and /r/MachineLearning
- [ ] Submit to Show HN
