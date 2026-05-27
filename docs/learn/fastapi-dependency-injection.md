# FastAPI dependency injection

FastAPI's `Depends(...)` is how Sentinel threads database sessions and
auth context through routes without globals.

## Async session pattern

```python
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_async_session

@router.get("/items")
async def list_items(session: AsyncSession = Depends(get_async_session)):
    ...
```

`get_async_session` is an async generator: it yields the session, commits
on clean exit, rolls back on exception. FastAPI evaluates the dependency
per request and runs the teardown when the response returns.

## Why we sometimes bypass it

Sentinel's `/v1/chat/completions` route opens `async with
AsyncSessionLocal()` directly instead of using `Depends`. The reason: the
route needs *multiple* short-lived sessions (resolve project → forward
upstream → record trace via a fire-and-forget task) and the request-scoped
session would hold a connection open for the duration of the LLM call.
Connections are precious; LLM calls take seconds.

## Header dependencies

`authorization: str = Header(None)` and `x_provider_key: str =
Header(None)` are dependency-injected from request headers. The dash-to-
underscore mapping is automatic; case-insensitive on the wire.
