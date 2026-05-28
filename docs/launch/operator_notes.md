# Phase 3 — Operator Notes

Strategic reminders from the user during Phase 3 / BYOK work. Read before
declaring Phase 3 done and before launch.

## 1. Verify Phase 2 actually shipped

Don't trust an "all complete" claim from any agentic IDE — including this
one. Before starting any new session, skim `git log --oneline -30`
yourself and spot-check that the commits cover what you think was done.

Session 0 (pre-flight audit) is designed to catch silent gaps, but a
60-second eyeball pass beats discovering the gap mid-Session-3.

Run these once between sessions:

```bash
git log --oneline -20
git status                       # working tree must match expectations
cd gateway && .venv/bin/python -m pytest -q --ignore=tests/test_judges.py
```

If any of these surprise you, pause and reconcile before continuing.

## 2. LLM provider credits before Session 0

The Session 0 verification step makes a **real** call to a provider.
Without credits it will fail and you'll waste 20 minutes debugging
something that isn't broken.

- **OpenAI is the cheapest option** — €5 covers every Phase 3 test cycle
  with room to spare.
- Add the key via `/settings/keys` (BYOK is now live) or env var
  `OPENAI_API_KEY` as a fallback.

## 3. Build-in-public — post BEFORE the demo video

When Session 4 wraps, BEFORE recording the full demo video, post a single
screenshot of the `/runs/[id]` trace-tree waterfall to LinkedIn:

> Building an open-source LangSmith alternative.
> Trace trees just landed.

Reasons:

- A single early post often outperforms the big launch post — the
  algorithm rewards momentum, not perfection.
- It starts gathering interest while you're still finishing the polish
  work, so by launch day there's a warm audience.
- Don't wait for everything to be perfect. Done > perfect, posted >
  done.

## 4. CV bullet (fill in after Session 5)

The bullet at the bottom of the Session 5 spec is the line meant for
your resume. After launch, fill in the actual numbers:

- **Routing benchmark**: the latency / cost-savings number from your
  own benchmark run, not the spec's placeholder.
- **GitHub stars**: post-launch count (check a week after launch — the
  curve flattens by then, so the number is more honest than day-1).

Don't ship the bullet with `{{X}}` placeholders.

## 5. Crash recovery — don't argue with the IDE

If a session crashes mid-way:

1. **Do not** try to coax the IDE back into a known-good state.
2. Stage everything currently in the working tree and commit it with a
   `wip:` prefix:
   ```bash
   git add -A
   git commit -m "wip: <short description of what was in-flight>"
   ```
3. **Close VS Code entirely.** Not the window — the whole app.
4. Reopen and start a fresh agent session, pointing it at that wip
   commit's SHA.

The Phase 3 session prompts are written to be resumable from any commit
on `main`, so a clean restart loses nothing except the broken context.
The wip commit can be amended or squashed away once you're back on
track.

---

Last updated during BYOK session (Phase 3, Session 1).
