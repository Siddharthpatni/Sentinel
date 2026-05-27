# JSONPath expressions

JSONPath is a query language for JSON, modeled after XPath. Sentinel uses
`jsonpath-ng` (the `.ext` parser, for filter expressions) in three places:
verification rule matching, routing policy matching, and eval assertion
extraction.

## Anatomy
- `$` — the root document.
- `.field` — child access. `$.choices[0].message.content` reaches into the
  OpenAI response shape.
- `[*]` — every element of an array.
- `..` — recursive descent. `$..content` finds every `content` key at any
  depth.
- `[?(@.role == "user")]` — filter on a predicate. Requires the `.ext`
  parser.

## Why this matters for Sentinel
Rules and policies are stored as strings (JSONB-friendly, no compile step at
write time). Compilation happens lazily on each match. Invalid JSONPath
raises at `parse(...)` — we always wrap in `try/except` and log+skip rather
than crashing the request path.

## Gotcha
The `messages` array carries the conversation. `$.messages[?(@.role ==
"user")]` filters to the user turn — most matching rules want this rather
than `$.messages[0]` (which would miss system-prompted requests).
