# Sentinel — demo video script

A 3-minute screen capture. Target audience: someone evaluating LLM
observability tools who has 3 minutes and a coffee. Goal: by the end, they
want to `git clone` it.

**Total length:** 3:00. **Format:** 1080p screen recording, voiceover.
**Tools:** OBS or QuickTime; the dashboard at `localhost:3000` and a
terminal running `docker compose up`.

---

## Storyboard

### [0:00–0:15] — Cold open: the pain

**Screen:** A terminal with someone making a `curl` to OpenAI.

**Voiceover:**
> "You shipped an LLM feature. Now you need to know what it cost yesterday,
> which user got the bad answer, and whether your EU compliance team is
> going to flag it. Your options today are: pay a SaaS, or build it
> yourself. I built a third one."

### [0:15–0:35] — Drop-in install

**Screen:** Run `docker compose up`. Cut to a code editor showing:

```python
from sentinel import OpenAI
client = OpenAI(base_url="http://localhost:8000", api_key="sk-sentinel-dev-000")
client.chat.completions.create(...)
```

**Voiceover:**
> "Sentinel is a self-hosted proxy. You change one URL in your OpenAI or
> Anthropic SDK call, point it at the gateway, and every request is now
> traced, costed, and stored locally."

### [0:35–1:00] — The traces dashboard

**Screen:** Open `localhost:3000`. The traces page loads. Make a chat
completion in a side terminal — the new trace flashes in within 3 seconds.
Hover the cost sparkline at the top of the page.

**Voiceover:**
> "This is the dashboard. Every call shows up live — model, latency,
> tokens, cost. The chart at the top is the last 24 hours of spend,
> bucketed by hour. No SaaS, no API key sent to a third party."

### [1:00–1:25] — Click into a trace

**Screen:** Click a trace row. Show the request body and response body
expanded.

**Voiceover:**
> "Click a trace and you get the full request and response. This is the
> single thing missing from provider dashboards — when a user reports a
> bad answer, you can find their exact prompt and the model's exact
> output."

### [1:25–1:50] — Verifications + Routing

**Screen:** Click the Verifications tab. Show one rule. Then Policies —
show a routing policy with two candidates.

**Voiceover:**
> "You can configure judge-based verifications — JSONPath matching, sample
> rates, judge model — to spot-check production quality. Routing
> policies let you fall back to a cheaper model on 5xx, or fan out
> to candidates."

### [1:50–2:15] — Evals + CI

**Screen:** Click Evals. Show a suite with a couple of runs. Cut to the
GitHub Action YAML.

**Voiceover:**
> "Eval suites are YAML. Run them in CI with the included GitHub Action;
> regressions fail the PR. The eval-trend graph shows pass-rate over time
> so you can spot the model update that broke your prompts."

### [2:15–2:40] — Audit (the big differentiator)

**Screen:** Click Audit. Create a classifier matching `$.messages[*]` with
tier `high`. Click "Verify chain" — show the green "OK · 42 entries"
result. Click "Export NDJSON" and show the file streaming.

**Voiceover:**
> "Here's the EU AI Act bit. Risk-tier classifiers tag inbound calls.
> Every tagged call is appended to a SHA-256-chained ledger that an
> auditor can verify offline. Tamper with any entry and every subsequent
> hash breaks. Streaming NDJSON export, server-side chain verification,
> done."

### [2:40–3:00] — Alerts + outro

**Screen:** Click Alerts. Show an alert "daily-burn cost > $1/hr". Hit
*check* — show "triggered" lighting up red.

**Voiceover:**
> "Threshold alerts are on cost, error rate, and p95 latency. Evaluated
> on demand — wire them to cron, Slack, or Datadog however you like.
>
> That's Sentinel. MIT licensed, runs on your laptop, has a Python SDK on
> PyPI. Link's in the description."

---

## Shot list (for editing)

| Shot | What | Approx duration |
| --- | --- | --- |
| A | Terminal: `docker compose up` | 5s |
| B | Editor: 5-line install snippet | 10s |
| C | Dashboard home — traces table + chart | 25s |
| D | Trace detail expanded | 25s |
| E | Verifications + Policies tour | 25s |
| F | Evals + GitHub Action YAML | 25s |
| G | Audit page — classifier, verify, export | 25s |
| H | Alerts page — create + check | 20s |
| I | Outro card with repo URL | 5s |

## Talking-point cheat sheet (if you don't use voiceover)

- Self-hosted. Drop-in. OpenAI + Anthropic.
- Postgres-backed traces. Live cost computation.
- Judge verifications, routing fallback, YAML evals, CI gate.
- **EU AI Act audit log with cryptographic chain.**
- Threshold alerts on cost / error / latency.
- Python SDK. MIT.
