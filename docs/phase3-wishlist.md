# Sentinel — Phase 3 Wishlist

> Capture every "we should do this later" thought during Phase 2. This file is the **primary input** for writing the Phase 3 Antigravity prompt. Don't trust memory — write it down the moment it occurs to you.

**Created:** 2026-05-26
**Phase 2 status when last updated:** Step 1 (models added, awaiting commit)

---

## How to use this file

1. While building Phase 2, every time you (or the agent) think "we should X later," append it to the relevant section below.
2. Don't filter at capture time — capture everything, filter later. A bad idea written down is better than a good idea forgotten.
3. Use the format: **What** (one line) · **Why** (one line) · **Trigger** (the moment that made you think of it).
4. When Phase 2 is done, review this file, group related items, and use it as the source for the Phase 3 spec.

---

## Already-locked Phase 3 scope (from original 3-month plan)

- [ ] Immutable AI Act audit log (append-only, cryptographic chaining)
- [ ] JSONL export per project per date range
- [ ] Configurable retention policies
- [ ] Per-trace risk-tier tagging (minimal / limited / high / unacceptable) driven by a rules file
- [ ] `/audit` dashboard page with export controls
- [ ] Cost charts on home page (Recharts area chart, last 30 days)
- [ ] Eval-trend lines on `/evals`
- [ ] Email alerting via SMTP on configurable rules (cost spike, error rate, eval regression)
- [ ] `docs/ai-act.md` mapping Sentinel features to AI Act articles

---

## New ideas surfaced during Phase 2

### Observability of Sentinel itself
-

### Schema improvements
- **What:** Retrofit a proper Alembic baseline (`001_initial.py`) and convert the Phase 2 models into a real `002_phase_2.py` migration.
  **Why:** Phase 1 ships with `create_all` only; without a baseline, future schema changes will be brittle.
  **Trigger:** Step 1 of Phase 2 — could not write `002_phase_2.py` because `001_initial.py` did not exist.

### Verification subsystem follow-ups
-

### Routing subsystem follow-ups
-

### Eval subsystem follow-ups
-

### Dashboard / UX improvements
-

### Performance issues observed
-

### Developer experience pain points
- **What:** Add CI step that runs `docker compose build` to catch `pyproject.toml` errors before deploy.
  **Why:** Phase 1 shipped with `hatchling.backends` typo and missing `[tool.hatch.build.targets.wheel]` — only caught when running locally.
  **Trigger:** First `docker compose up` of Phase 2 failed at build time.

### Documentation gaps
-

### Security concerns deferred
-

---

## Architectural decisions to revisit

| Date | Decision made | Alternative considered | Why might want to revisit |
|------|---------------|------------------------|---------------------------|
| 2026-05-26 | Use `create_all` for Phase 2 tables | Write proper Alembic 002 migration | Phase 1 has no Alembic baseline; deferring forces brittle ad-hoc schema changes |

---

## Dependencies you wish you'd added
-

---

## Features users (or you, as a user) asked for

| Date | Who | What they wanted | How strongly |
|------|-----|------------------|--------------|
| | | | |

---

## Things that turned out to be more important than expected
-

## Things that turned out to be less important than expected
-

---

## Pre-Phase-3 grooming checklist

- [ ] Read this entire file end-to-end
- [ ] Cluster related items into themes
- [ ] Drop items that no longer matter
- [ ] For each remaining cluster, decide: Phase 3? Phase 4? Never?
- [ ] Sketch the Phase 3 prompt structure (mission, constraints, tables, subsystems, build order, acceptance criteria)
- [ ] Run the resulting wishlist by someone technical for sanity check
- [ ] Then, and only then, write the Phase 3 Antigravity prompt
