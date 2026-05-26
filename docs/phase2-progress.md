# Sentinel Phase 2 — Progress Tracker

> Living document. Update as each step lands. The goal: when Phase 3 is written, this file is the ground truth for what was actually built vs what the spec promised.

**Started:** _<date>_
**Target completion:** _<date>_
**Current step:** _<number / name>_

---

## Step status

| # | Step | Status | Commit | Date | Notes |
|---|------|--------|--------|------|-------|
| 1 | Migration 002 (5 new tables) | ☐ | | | |
| 2 | Verification rules model + CRUD | ☐ | | | |
| 3 | Judge module (Jinja2 + structured output) | ☐ | | | |
| 4 | Verification orchestrator Celery task | ☐ | | | |
| 5 | `/api/verifications` GET endpoint | ☐ | | | |
| 6 | Dashboard `/verifications` page | ☐ | | | |
| 7 | Routing policy model + CRUD | ☐ | | | |
| 8 | Routing middleware + fallback | ☐ | | | |
| 9 | Dashboard `/policies` page | ☐ | | | |
| 10 | Eval YAML parser + assertion engine | ☐ | | | |
| 11 | Eval runner | ☐ | | | |
| 12 | `/api/evals/*` endpoints | ☐ | | | |
| 13 | Dashboard `/evals/*` pages | ☐ | | | |
| 14 | CI integration script | ☐ | | | |
| 15 | Docs + README update | ☐ | | | |

Statuses: ☐ not started · 🔄 in progress · ⏸ blocked · ✓ done

---

## Deviations from spec

| Date | What changed | Why | Spec section |
|------|--------------|-----|--------------|
| | | | |

---

## Metrics snapshot (update weekly)

| Date | LOC backend | LOC frontend | Test coverage | CI duration | Open TODOs |
|------|-------------|--------------|---------------|-------------|------------|
| | | | | | |

```bash
tokei gateway/app sdk/sentinel dashboard/app dashboard/components
pytest gateway/tests --cov=app --cov-report=term | tail -3
grep -rn "TODO\|FIXME" gateway/app sdk/sentinel dashboard/app dashboard/components | wc -l
```

---

## Blockers log

| Date opened | Step | Blocker | Resolved? | Resolution / workaround |
|-------------|------|---------|-----------|-------------------------|
| | | | | |

---

## Things the agent did well

-

## Things the agent did badly

-

---

## Test results history

```
Step 1:
...
```

---

## Demo-readiness checklist

- [ ] All 15 steps committed to `main`
- [ ] CI green on `main`
- [ ] All learning notes written and indexed
- [ ] Three new dashboard pages screenshot-ready
- [ ] Example verification rule, routing policy, and eval suite seeded in default project
- [ ] `docker compose up` on a fresh clone works end-to-end
- [ ] Quickstart in README still accurate
- [ ] 2-minute demo script written

---

## Sign-off

- [ ] All acceptance criteria from section 8 of the Phase 2 prompt are met
- [ ] This tracker is fully filled in
- [ ] `docs/phase3-wishlist.md` has at least 5 substantive entries
- [ ] Demo video recorded and linked in README
