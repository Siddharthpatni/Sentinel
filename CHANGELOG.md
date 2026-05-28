# Changelog

All notable changes to Sentinel are recorded here. Dates are UTC.

## [Unreleased] — Phase 3

### Added — Session 4: Dashboard polish (2026-05-28)
- Shared UI primitives: `ToastProvider`, `ErrorBanner`, `EmptyState`,
  `TableSkeleton`. `alert()` replaced everywhere with toasts
- Traces page: provider/model/status filter bar, visible-window cost +
  token rollup, j/k/↵ keyboard nav with focus ring
- Retryable error banners replace bare `String(e)` on sessions /
  datasets / annotations / playground / traces
- Shimmer skeletons replace bare "Loading…" text across list pages
- Light-theme polish: glass-panel solid bg + shadow, json-viewer
  contrast, badge contrast for openai/anthropic providers
- Zero-state hero on `/` with SDK + curl snippets and `make demo` hint

### Added — Session 3: Playground / Datasets / Annotation queue
- `Dataset` + `DatasetItem` DB models with unique `(project_id, name)`
- `/api/datasets` CRUD: list (with item counts), create, patch, delete;
  item add/list/delete with optional `source_trace_id` linkback
- `/datasets` index + `/datasets/[id]` detail (collapsible items)
- `/playground` — chat editor with project picker, model datalist,
  message editor (system/user/assistant), save-to-dataset (existing or
  inline new). `sessionStorage` prefill for trace-replay
- `GET /api/traces/queues/unannotated` (NOT-IN subquery on
  `trace_annotations`) and `/annotations` queue page
- `TraceActions` on `/traces/[id]`: "Replay in playground" +
  "Add to dataset" inline picker

### Added — Session 2: Span trees / waterfall
- `Span` DB model with self-referential `parent_span_id` for tree
  structure, indexed on `trace_id` + `parent_span_id`
- `sentinel.trace(...)` SDK context manager with contextvar-based span
  nesting; `t.span(name, span_type=..., **attrs)` opens children;
  `SpanRecord.to_wire()` JSON serialization
- `POST /api/traces/{trace_id}/spans` batch ingest; flushed at trace
  end (silent failure — tracing never breaks user code)
- `SpanWaterfall` Gantt renderer on `/traces/[id]` with type colors
  (agent / llm / tool) and click-to-expand attributes panel
- `examples/playwright_agent.py` rewritten to emit a real span tree per
  visited URL

### Added — Session 1: BYOK provider credentials
- `ProviderCredential` model with Fernet-encrypted secrets;
  alembic migration 003
- `keyvault.py` — encrypt / decrypt / fingerprint / redact helpers wired
  into the structlog pipeline (no plaintext keys ever logged)
- `/api/credentials` CRUD scoped per project
- `POST /api/credentials/{id}/test` — live-validate stored keys against
  the provider's model-list endpoint (no token cost)
- Adapters now require `x-provider-key` resolved from per-project
  keyvault; settings fallback removed
- `/settings/keys` dashboard page
- Light mode via CSS-variable theming (`html.light` overrides);
  theme toggle in the nav bar

### Added — Demo readiness (2026-05-28)
- `examples/seed_demo.py` — populates a fresh stack with ~12 varied
  traces (two sessions, one intentional error), a 4-span agent trace,
  a routing policy, a verification rule, and a dataset. Total OpenAI
  cost <$0.01
- `scripts/demo.sh` + `Makefile` — `make demo` boots compose, waits for
  gateway health, installs the SDK, runs the seed, and opens the
  dashboard. Idempotent
- `Makefile` targets: `up`, `down`, `seed`, `logs`, `test`, `lint`
- README rewrite: 30-second pitch, feature matrix vs. LangSmith /
  Langfuse / Phoenix, two-path quickstart (`make demo` vs. BYO traffic)

## [Phase 1+2] — baseline
- Observability proxy: OpenAI/Anthropic adapters, trace persistence,
  cost + latency metrics, live dashboard, cost-over-time sparkline
- Evals: YAML suite definitions, 7 assertion types, run history, CI
  entrypoint
- Routing policies + provider fallback (3 attempts max, streaming
  bypass)
- Annotations: thumbs-up/down + comment per trace
- Sessions: conversation threads via `_sentinel.session_id` metadata
- EU AI Act audit log: risk-tier classifiers, SHA-256-chained ledger,
  NDJSON export, server-side verify
- Threshold alerts on cost-per-hour, error-rate, p95 latency
- Verifications: declarative judge-model rules with sampling
