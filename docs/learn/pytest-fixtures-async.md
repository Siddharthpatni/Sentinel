# pytest fixtures for async code

Sentinel's gateway is async (FastAPI + SQLAlchemy async). Tests need to
spin up an async session, an HTTP client, and tear them down without
leaking connections.

## The setup

```python
# conftest.py
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

@pytest_asyncio.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
```

`@pytest_asyncio.fixture` (from `pytest-asyncio`) makes the fixture an
async generator. The `yield` mid-function is the standard pattern: setup
above, teardown below.

## Session scope

By default each test gets a fresh fixture. For an expensive setup
(database creation), use `scope="session"`:

```python
@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()
```

## The gotcha

`asyncio_mode = "auto"` in `pyproject.toml` removes the need for
`@pytest.mark.asyncio` on every test. Without it, tests with `async def`
silently skip — they don't fail, they don't error, they just say "passed"
having executed zero code.
