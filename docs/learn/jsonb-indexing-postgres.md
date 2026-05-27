# JSONB indexing in Postgres

Sentinel stores three high-traffic JSONB columns: `traces.request_body`,
`traces.response_body`, and `routing_policies.candidates`. JSONB without
indexes is fine for *storing* — but queries that filter on JSON keys do a
sequential scan unless the right index exists.

## GIN: the default

```sql
CREATE INDEX ix_traces_request_body_gin
  ON traces USING gin (request_body jsonb_path_ops);
```

`jsonb_path_ops` is smaller and faster than the default `jsonb_ops` if you
only need containment (`@>`). Sentinel uses containment for "find traces
matching this JSONPath" approximations.

## Expression indexes for hot paths

If one specific key is always queried (e.g. `request_body->>'model'`), an
expression index on that key beats GIN:

```sql
CREATE INDEX ix_traces_model_jsonb
  ON traces ((request_body->>'model'));
```

## Don't index everything

GIN indexes are expensive to maintain on write. Sentinel's traces table is
write-heavy (every API call → one row). We index `created_at`,
`project_id`, `provider`, `model` (plain B-tree), and only consider GIN
indexes when a specific query pattern emerges from production.
