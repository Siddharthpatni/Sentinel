# Structured output from LLMs

Sentinel's verification subsystem asks a judge model "did the response
satisfy this rule?" and parses the reply. We use OpenAI's
`response_format: {"type": "json_object"}` to constrain the judge to emit
JSON, but constraint is not the same as guarantee — models still wrap the
JSON in markdown fences, prefix it with prose, or close their output mid-
object.

## Defensive parsing

`parse_judge_response` in `app/verification/judges.py`:

1. Try `json.loads(text)` directly.
2. If that fails, regex-extract the first `{...}` substring and try again.
3. If still failing, record `verdict="error"` with the raw text — we'd
   rather skip a verification than crash the orchestrator.

## Validation

Even valid JSON can be semantically wrong: `{"verdict": "yes"}` is parseable
but doesn't fit the expected `agree|disagree|uncertain` set. We validate the
shape (`verdict` in the allowed set, `confidence` in [0,1]) and downgrade
violators to `verdict="error"`.

## Cost lever

Judge calls are real LLM calls — they cost real money and are themselves
traced. Sample-rate (`sample_rate` on each verification rule) keeps the
verification cost bounded relative to primary traffic.
