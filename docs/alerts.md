# Alerts

Threshold checks on the metrics most teams want a Slack-ping for:

| Metric | Unit | Notes |
| --- | --- | --- |
| `cost_per_hour_usd` | USD/hour | Spend normalized to a per-hour rate over the window. |
| `error_rate_pct` | percent | `count(status_code >= 400) / count(*) * 100`. |
| `latency_p95_ms` | ms | `percentile_cont(0.95)` over `latency_ms`. |

Each alert has a `window_minutes` rolling lookback, a `threshold`, and a
comparator (`gt` or `lt`). Alerts are evaluated **on demand** — there is no
background scheduler. You hit `POST /api/alerts/{id}/check` (or click
*check* in the dashboard) and Sentinel computes the current value, persists
it on the row, and tells you whether the threshold tripped.

This deliberate on-demand model keeps the gateway dependency-light. To get
push-style alerting wire `check` to whatever you already use (cron + curl,
Slack webhook, Datadog synthetic monitor, etc.).

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/alerts` | Create an alert |
| `GET` | `/api/alerts?project_id=...` | List alerts for a project |
| `PATCH` | `/api/alerts/{id}` | Update fields |
| `DELETE` | `/api/alerts/{id}` | Delete |
| `POST` | `/api/alerts/{id}/check` | Evaluate now and persist the result |

## SDK

```python
from sentinel import Sentinel
s = Sentinel(url="http://localhost:8000", api_key="sk-sentinel-dev-000")

alert = s.alerts.create(
    project_id=project_id,
    name="daily-burn",
    metric="cost_per_hour_usd",
    threshold=1.50,           # USD / hour
    window_minutes=60,
)

result = s.alerts.check(alert["id"])
if result["triggered"]:
    notify_slack(f"{alert['name']} tripped: {result['value']:.2f} > {result['threshold']:.2f}")
```

## Worth knowing

- The window doesn't reset on a calendar boundary — it's a true rolling window
  ending at "now". `window_minutes=60` means "the last 60 minutes from the
  instant you called check."
- `last_value` and `last_triggered` are snapshots from the last `check` call,
  not live values. The dashboard `state` column reflects the last check.
- `cost_per_hour_usd` is normalized — a $0.50 spend over 30 minutes reports
  as `1.0 USD/hour`. This makes thresholds window-independent.
