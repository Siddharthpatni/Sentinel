# Audit log & EU AI Act compliance

The EU AI Act (in force from 2026) requires deployers of "high-risk" AI
systems to keep tamper-evident logs of every automated decision, with the
input, the model, the output, and the assigned risk tier. Sentinel ships
this out of the box.

## How it works

1. **Risk-tier classifiers** map request shapes to one of the four EU AI
   Act tiers: `unacceptable`, `high`, `limited`, `minimal`. A classifier
   is a JSONPath expression — the first matching, enabled classifier wins.
   No classifier matches ⇒ `risk_tier=NULL` (treat as `minimal`).

2. **At ingest** the gateway evaluates classifiers against the request
   body before forwarding, records the resulting tier on the `traces` row,
   and appends an **audit ledger entry** for the trace.

3. **The audit ledger** (`audit_log` table) is append-only and chained:

   ```
   entry_hash = SHA256(canonical_json({
       sequence, project_id, trace_id, risk_tier, payload, prev_hash
   }))
   ```

   Each entry's `prev_hash` is the previous entry's `entry_hash`. Tampering
   with any entry breaks every subsequent hash, so a single comparison run
   over an export is enough to detect modification.

4. **Export** (`GET /api/audit/export`) streams the ledger as NDJSON with
   one entry per line, including the hashes. An external auditor recomputes
   `entry_hash` for each line and compares.

5. **Verify** (`GET /api/audit/verify`) does the same check server-side
   and reports the first inconsistency it finds.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/audit/classifiers` | Create a tier classifier |
| `GET` | `/api/audit/classifiers?project_id=...` | List |
| `PATCH` | `/api/audit/classifiers/{id}` | Update |
| `DELETE` | `/api/audit/classifiers/{id}` | Delete |
| `GET` | `/api/audit/export?project_id=...` | Stream NDJSON ledger |
| `GET` | `/api/audit/verify?project_id=...` | Server-side chain verify |

## Example: tag every recruiting request as high-risk

```python
from sentinel import Sentinel
s = Sentinel(url="http://localhost:8000", api_key="sk-sentinel-dev-000")

s.audit.create_classifier(
    project_id=project_id,
    name="recruiting-high-risk",
    match_jsonpath='$.messages[?(@.content =~ ".*(candidate|resume|cv).*")]',
    risk_tier="high",
)
```

From this point every chat completion whose user/system content mentions
candidates, resumes, or CVs is recorded with `risk_tier="high"` on its
trace and on its audit ledger entry.

## Export and verify

```python
entries = s.audit.export(project_id=project_id, risk_tier="high")
print(f"{len(entries)} high-risk decisions logged")

print(s.audit.verify(project_id=project_id))
# {'ok': True, 'checked': 42, 'error': None}
```

## What the ledger does *not* do

- **Cryptographic signing.** The chain proves tamper-evidence, not
  authenticity. If you need to prove the ledger was written by Sentinel
  and not forged, pair this with external timestamping (RFC 3161) or a
  blockchain anchor — both out of scope here.
- **PII redaction.** The ledger snapshots the request/response bodies
  verbatim. Strip PII at ingest if you have to keep ledger storage out of
  the GDPR data-subject scope.
- **GDPR right-to-erasure.** Erasure conflicts with the AI Act's
  retention obligations. The standard workaround is to redact the
  `payload` JSON in-place and re-derive `entry_hash` (which breaks the
  chain forward intentionally — proof that erasure happened, not that it
  didn't).
