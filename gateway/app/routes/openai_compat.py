"""OpenAI-compatible gateway route: /v1/chat/completions."""

from __future__ import annotations

import json
import logging
import time

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select

from app.config import settings
from app.db.models import Project
from app.db.session import AsyncSessionLocal
from app.providers.openai import OpenAIAdapter
from app.tracing.cost import compute_cost
from app.tracing.recorder import record_trace
from app.tracing.schema import TraceCreate

logger = logging.getLogger(__name__)
router = APIRouter()

adapter = OpenAIAdapter()


async def _resolve_project(api_key: str) -> Project:
    """Look up the project by API key, raising 401 if not found."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Project).where(Project.api_key == api_key)
        )
        project = result.scalar_one_or_none()
        if project is None:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return project


def _extract_api_key(authorization: str | None) -> str:
    """Extract the Bearer token from the Authorization header."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization format")
    return parts[1]


@router.post("/v1/chat/completions", response_model=None)
async def chat_completions(
    request: Request,
    authorization: str | None = Header(None),
    x_provider_key: str | None = Header(None),
) -> JSONResponse | StreamingResponse:
    """Forward a chat completion request to OpenAI and log the trace."""
    api_key = _extract_api_key(authorization)
    project = await _resolve_project(api_key)

    body = await request.json()
    is_stream = body.get("stream", False)

    provider_headers = {
        "x-provider-key": x_provider_key or settings.openai_api_key,
    }

    if is_stream:
        return await _handle_stream(project, body, provider_headers)

    return await _handle_non_stream(project, body, provider_headers)


async def _handle_non_stream(
    project: Project,
    body: dict,
    headers: dict[str, str],
) -> JSONResponse:
    """Process a non-streaming chat completion request."""
    start = time.monotonic()
    resp = await adapter.forward(body, headers)
    latency_ms = int((time.monotonic() - start) * 1000)

    cost = compute_cost(resp.model, resp.prompt_tokens, resp.completion_tokens)

    trace = TraceCreate(
        project_id=project.id,
        provider="openai",
        model=resp.model,
        latency_ms=latency_ms,
        prompt_tokens=resp.prompt_tokens,
        completion_tokens=resp.completion_tokens,
        cost_usd=cost.total_cost_usd,
        status_code=resp.status_code,
        request_body=body,
        response_body=resp.body,
        error_message=resp.error_message,
    )
    record_trace(trace)

    return JSONResponse(content=resp.body, status_code=resp.status_code)


async def _handle_stream(
    project: Project,
    body: dict,
    headers: dict[str, str],
) -> StreamingResponse:
    """Process a streaming chat completion request."""
    buffer: list[bytes] = []
    buffer_size = 0
    buffer_capped = False
    start = time.monotonic()

    async def stream_and_capture():  # type: ignore[no-untyped-def]
        nonlocal buffer_size, buffer_capped
        async for chunk in adapter.forward_stream(body, headers):
            if not buffer_capped:
                buffer_size += len(chunk)
                if buffer_size <= settings.max_stream_buffer_bytes:
                    buffer.append(chunk)
                else:
                    buffer_capped = True
                    logger.warning(
                        "Stream buffer exceeded %d bytes, dropping response capture",
                        settings.max_stream_buffer_bytes,
                    )
            yield chunk

    async def stream_wrapper():  # type: ignore[no-untyped-def]
        async for chunk in stream_and_capture():
            yield chunk

        # After streaming completes, parse usage and log trace
        latency_ms = int((time.monotonic() - start) * 1000)
        prompt_tokens = 0
        completion_tokens = 0
        model = body.get("model", "unknown")

        # Parse SSE chunks for usage data
        for raw in buffer:
            line = raw.decode("utf-8", errors="replace").strip()
            if line.startswith("data: ") and line != "data: [DONE]":
                try:
                    chunk_data = json.loads(line[6:])
                    if chunk_data.get("usage"):
                        prompt_tokens = chunk_data["usage"].get("prompt_tokens", 0)
                        completion_tokens = chunk_data["usage"].get("completion_tokens", 0)
                    if "model" in chunk_data:
                        model = chunk_data["model"]
                except json.JSONDecodeError:
                    pass

        cost = compute_cost(model, prompt_tokens, completion_tokens)

        # Reconstruct response from buffer if possible
        response_body = None
        if not buffer_capped:
            try:
                full_text = b"".join(buffer).decode("utf-8", errors="replace")
                response_body = {"_streamed_chunks": full_text[:50000]}  # Cap stored text
            except Exception:
                pass

        trace = TraceCreate(
            project_id=project.id,
            provider="openai",
            model=model,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost.total_cost_usd,
            status_code=200,
            request_body=body,
            response_body=response_body,
            error_message=None,
        )
        record_trace(trace)

    return StreamingResponse(
        stream_wrapper(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
