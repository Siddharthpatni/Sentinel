"""Anthropic-compatible gateway route: /v1/messages."""

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
from app.providers.anthropic import AnthropicAdapter
from app.tracing.cost import compute_cost
from app.tracing.recorder import record_trace
from app.tracing.schema import TraceCreate

logger = logging.getLogger(__name__)
router = APIRouter()

adapter = AnthropicAdapter()


async def _resolve_project(api_key: str) -> Project:
    """Look up the project by Sentinel API key."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Project).where(Project.api_key == api_key)
        )
        project = result.scalar_one_or_none()
        if project is None:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return project


@router.post("/v1/messages")
async def create_message(
    request: Request,
    x_sentinel_key: str | None = Header(None),
    authorization: str | None = Header(None),
    x_provider_key: str | None = Header(None),
) -> JSONResponse | StreamingResponse:
    """Forward a message creation request to Anthropic and log the trace.

    Accepts authentication via either ``x-sentinel-key`` header or
    ``Authorization: Bearer <key>`` header.
    """
    # Resolve Sentinel API key from either header
    sentinel_key = x_sentinel_key
    if not sentinel_key and authorization:
        parts = authorization.split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            sentinel_key = parts[1]

    if not sentinel_key:
        raise HTTPException(status_code=401, detail="Missing Sentinel API key")

    project = await _resolve_project(sentinel_key)

    body = await request.json()
    is_stream = body.get("stream", False)

    provider_headers = {
        "x-provider-key": x_provider_key or settings.anthropic_api_key,
    }

    if is_stream:
        return await _handle_stream(project, body, provider_headers)

    return await _handle_non_stream(project, body, provider_headers)


async def _handle_non_stream(
    project: Project,
    body: dict,
    headers: dict[str, str],
) -> JSONResponse:
    """Process a non-streaming Anthropic message request."""
    start = time.monotonic()
    resp = await adapter.forward(body, headers)
    latency_ms = int((time.monotonic() - start) * 1000)

    cost = compute_cost(resp.model, resp.prompt_tokens, resp.completion_tokens)

    trace = TraceCreate(
        project_id=project.id,
        provider="anthropic",
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
    """Process a streaming Anthropic message request."""
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
                    logger.warning("Stream buffer exceeded cap, dropping response capture")
            yield chunk

    async def stream_wrapper():  # type: ignore[no-untyped-def]
        async for chunk in stream_and_capture():
            yield chunk

        # Parse Anthropic SSE for usage data
        latency_ms = int((time.monotonic() - start) * 1000)
        prompt_tokens = 0
        completion_tokens = 0
        model = body.get("model", "unknown")

        for raw in buffer:
            line = raw.decode("utf-8", errors="replace").strip()
            if line.startswith("data: "):
                try:
                    chunk_data = json.loads(line[6:])
                    # Anthropic sends usage in message_start and message_delta events
                    if chunk_data.get("type") == "message_start":
                        msg = chunk_data.get("message", {})
                        usage = msg.get("usage", {})
                        prompt_tokens = usage.get("input_tokens", 0)
                        model = msg.get("model", model)
                    elif chunk_data.get("type") == "message_delta":
                        usage = chunk_data.get("usage", {})
                        completion_tokens = usage.get("output_tokens", 0)
                except json.JSONDecodeError:
                    pass

        cost = compute_cost(model, prompt_tokens, completion_tokens)

        response_body = None
        if not buffer_capped:
            try:
                full_text = b"".join(buffer).decode("utf-8", errors="replace")
                response_body = {"_streamed_chunks": full_text[:50000]}
            except Exception:
                pass

        trace = TraceCreate(
            project_id=project.id,
            provider="anthropic",
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
