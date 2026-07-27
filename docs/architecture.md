# Sentinel Architecture

See the [root README](../README.md#architecture) for the service diagram
and port table. This page covers the gateway overhead benchmark cited
there.

## Benchmark methodology

Measured locally against `qwen2.5-coder:7b` on Ollama (no network hop —
isolates gateway processing time from provider round-trip variance, which
would otherwise dominate the signal). 15 sequential requests per side,
`max_tokens: 5`, median reported (min/max discarded — LLM inference time
itself is not fully deterministic even at a fixed token count, so a mean
would conflate that noise with actual proxy overhead).

```
direct  (Ollama, no proxy):  196ms median  (188ms best-case)
gateway (via Sentinel):      232ms median  (215ms best-case)
overhead:                    +36ms median  (+27ms best-case)
```

The +36ms covers: API-key resolution, audit-classifier match, routing-
policy lookup, and forwarding the request — trace persistence happens
async via Celery, off the request path, so it doesn't add to this number.

Reproduce it:

```bash
# terminal 1
ollama serve

# terminal 2 — direct
for i in $(seq 15); do
  curl -s -o /dev/null -w "%{time_total}\n" http://localhost:11434/v1/chat/completions \
    -d '{"model":"qwen2.5-coder:7b","messages":[{"role":"user","content":"Say OK"}],"max_tokens":5}'
done

# via gateway (after `make up`)
for i in $(seq 15); do
  curl -s -o /dev/null -w "%{time_total}\n" http://localhost:8000/v1/chat/completions \
    -H "Authorization: Bearer sk-sentinel-dev-000" \
    -d '{"model":"ollama/qwen2.5-coder:7b","messages":[{"role":"user","content":"Say OK"}],"max_tokens":5}'
done
```

Numbers will vary by machine — what should hold is the *shape*: gateway
overhead in the tens-of-milliseconds range, not hundreds, since there's no
second network hop to a hosted backend.
