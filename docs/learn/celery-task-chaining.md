# Celery task chaining

Sentinel runs two background tasks per primary trace:

1. `persist_trace_task` — write the trace row to Postgres.
2. `evaluate_trace` — orchestrate verification rules against the persisted
   row.

Step 2 must run *after* step 1 commits. Naively kicking off both with
`.delay()` from the gateway risks the verifier loading a non-existent trace.

## How we chain

`persist_trace_task` calls `evaluate_trace.delay(str(trace.id))` *inside*
its `try` block after `session.commit()`. This is not Celery's built-in
`chain(...)` primitive — it's a manual fire-and-forget enqueue from inside
the parent task. We chose it because:

- Sentinel's verifier is fully decoupled: a failure here must never roll
  back the trace.
- `chain(...)` requires both signatures up front, which couples the
  enqueuer to the verifier's signature.

## Idempotency

Both tasks have `acks_late=True` and bounded retries. If the worker dies
mid-execution, the broker re-delivers — so the task must be safe to run
twice. We give traces a `uuid4()` at creation, so duplicate inserts would
violate the PK and fail loudly rather than silently double-write.

## Module registration

Celery only imports modules listed in `include=[...]` or matching the
`tasks.py` naming convention for `autodiscover_tasks`. Sentinel uses
explicit `include` because our tasks live in `persist_trace.py` and
`evaluate_trace.py`, not `tasks.py`.
