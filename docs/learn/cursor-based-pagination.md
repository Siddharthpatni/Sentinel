# Cursor-based pagination

Sentinel's trace list endpoint returns the most recent N traces. Offset
pagination (`LIMIT 50 OFFSET 200`) becomes pathological at scale: Postgres
still has to scan and discard the first 200 rows, and the result is
inconsistent if new rows arrive between requests.

## The cursor pattern

A cursor is an opaque token derived from the last row's sort key. For
Sentinel, the sort key is `created_at`:

```python
query = select(Trace).order_by(Trace.created_at.desc()).limit(limit + 1)
if cursor:
    query = query.where(Trace.created_at < decode_cursor(cursor))
rows = (await session.execute(query)).scalars().all()
next_cursor = encode_cursor(rows[limit].created_at) if len(rows) > limit else None
```

We fetch one extra row to detect whether a next page exists without a
second `COUNT(*)`.

## Index alignment

Cursor pagination only beats offset if the cursor column is indexed. We
have `ix_traces_created_at` on the traces table.

## Tie-breakers

When the cursor column isn't unique, ties cause skipped or duplicated rows
across pages. Pair the cursor with the primary key:
`WHERE (created_at, id) < (cursor_ts, cursor_id)`. Sentinel's `created_at`
has microsecond resolution and traces arrive sub-microsecond rarely, so
we accept the risk for now.
