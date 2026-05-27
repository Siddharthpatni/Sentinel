# Server-sent events for streaming

LLM responses can be slow — tens of seconds is normal. Streaming lets the
client render tokens as they arrive instead of waiting for the full
response. OpenAI's API uses Server-Sent Events (SSE) for this, and Sentinel
forwards SSE end-to-end.

## The wire format

```
data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n
data: {"choices":[{"delta":{"content":" world"}}]}\n\n
data: [DONE]\n\n
```

Each `data:` line is a JSON chunk, terminated by `\n\n`. The terminal
`[DONE]` sentinel signals stream end.

## FastAPI integration

```python
from fastapi.responses import StreamingResponse

return StreamingResponse(
    generator(),
    media_type="text/event-stream",
    headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",  # disable nginx buffering
    },
)
```

`X-Accel-Buffering: no` matters when fronted by nginx/Cloudflare —
otherwise the proxy buffers chunks and the client sees the whole response
at once, defeating the point.

## Sentinel's tee pattern

We need to forward chunks to the client *and* capture them for tracing.
The pattern: `async for chunk in upstream: buffer.append(chunk); yield
chunk`. After the upstream generator exits, the wrapper parses the buffer
for `usage` data and emits a trace row. A buffer cap (`max_stream_buffer_
bytes`) prevents unbounded memory on rogue responses.
