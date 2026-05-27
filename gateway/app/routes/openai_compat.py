"""OpenAI-compatible gateway route: /v1/chat/completions."""

from __future__ import annotations

import json
import logging
import time

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select

from app.audit.classifiers import classify
from app.config import settings
from app.db.models import AuditClassifier, Project
from app.db.session import AsyncSessionLocal
from app.providers.openai import OpenAIAdapter
from app.providers.openrouter import OpenRouterAdapter
from app.routes.annotations import resolve_session_id
from app.routing.middleware import (
    apply_candidate,
    consume_candidate,
    select_route,
    should_fall_back,
)
from app.tracing.cost import compute_cost
from app.tracing.recorder import record_trace
from app.tracing.schema import TraceCreate

logger = logging.getLogger(__name__)
router = APIRouter()

adapter = OpenAIAdapter()
openrouter_adapter = OpenRouterAdapter()


def _select_adapter(model: str) -> tuple[OpenAIAdapter | OpenRouterAdapter, str, str]:
    """Pick the upstream adapter from the model string.

    Convention: prefix the model with ``openrouter/`` to route through
    OpenRouter, e.g. ``openrouter/anthropic/claude-3-haiku``. The prefix is
    stripped before the upstream call. Returns (adapter, upstream_model,
    provider_name).
    """
    if model.startswith("openrouter/"):
        return openrouter_adapter, model.removeprefix("openrouter/"), "openrouter"
    return adapter, model, "openai"


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


async def _classify_request(project_id, body: dict) -> str | None:  # type: ignore[no-untyped-def]
    """Run audit classifiers against the request body. Returns risk_tier or None."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AuditClassifier)
            .where(
                AuditClassifier.project_id == project_id,
                AuditClassifier.enabled.is_(True),
            )
            .order_by(AuditClassifier.name)
        )
        classifiers = result.scalars().all()
    return classify(body, classifiers)


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

    risk_tier = await _classify_request(project.id, body)
    session_id = await resolve_session_id(project.id, body)

    requested_model = body.get("model", "")
    selected_adapter, upstream_model, provider_name = _select_adapter(requested_model)
    if upstream_model != requested_model:
        body = {**body, "model": upstream_model}

    default_key = (
        settings.openrouter_api_key
        if provider_name == "openrouter"
        else settings.openai_api_key
    )
    provider_headers = {
        "x-provider-key": x_provider_key or default_key,
    }

    if is_stream:
        return await _handle_stream(
            project, body, provider_headers, selected_adapter, provider_name, risk_tier, session_id
        )

    # Routing middleware (non-streaming only — streaming bypass per spec).
    # Judge-tagged requests skip routing to avoid recursion.
    is_judge = bool(body.get("_sentinel", {}).get("is_judge"))
    if not is_judge:
        async with AsyncSessionLocal() as session:
            route = await select_route(session, project.id, body)
        if route.candidates_remaining:
            return await _handle_non_stream_with_route(
                project, body, provider_headers, route, risk_tier, session_id
            )

    return await _handle_non_stream(
        project, body, provider_headers, selected_adapter, provider_name, risk_tier, session_id
    )


async def _handle_non_stream_with_route(
    project: Project,
    body: dict,
    headers: dict[str, str],
    route,  # type: ignore[no-untyped-def]
    risk_tier: str | None = None,
    session_id=None,
) -> JSONResponse:
    """Try candidates in order; on 5xx (or other fallback condition) try the next.

    Each attempt is its own trace; provenance is recorded on the trace's
    request_body under ``_sentinel.route``.
    """
    last_resp = None
    attempt = 0
    fallback_on = {"http_5xx": True}

    while route.candidates_remaining and attempt < 3:
        attempt += 1
        attempt_body = apply_candidate(body, route, attempt)
        adapter, upstream_model, provider_name = _select_adapter(
            attempt_body.get("model", "")
        )
        if upstream_model != attempt_body["model"]:
            attempt_body = {**attempt_body, "model": upstream_model}

        start = time.monotonic()
        resp = await adapter.forward(attempt_body, headers)
        latency_ms = int((time.monotonic() - start) * 1000)

        cost = compute_cost(resp.model, resp.prompt_tokens, resp.completion_tokens)
        record_trace(
            TraceCreate(
                project_id=project.id,
                provider=provider_name,
                model=resp.model,
                latency_ms=latency_ms,
                prompt_tokens=resp.prompt_tokens,
                completion_tokens=resp.completion_tokens,
                cost_usd=cost.total_cost_usd,
                status_code=resp.status_code,
                request_body=attempt_body,
                response_body=resp.body,
                error_message=resp.error_message,
                risk_tier=risk_tier,
                session_id=session_id,
            )
        )

        last_resp = resp
        if not should_fall_back(resp.status_code, fallback_on):
            return JSONResponse(content=resp.body, status_code=resp.status_code)
        consume_candidate(route)
        logger.info(
            "Routing fallback: candidate %d (%s) returned %d, trying next",
            attempt, upstream_model, resp.status_code,
        )

    # All attempts exhausted
    if last_resp is None:
        raise HTTPException(status_code=502, detail="No routing candidates available")
    return JSONResponse(content=last_resp.body, status_code=last_resp.status_code)


async def _handle_non_stream(
    project: Project,
    body: dict,
    headers: dict[str, str],
    selected_adapter: OpenAIAdapter | OpenRouterAdapter,
    provider_name: str,
    risk_tier: str | None = None,
    session_id=None,
) -> JSONResponse:
    """Process a non-streaming chat completion request."""
    start = time.monotonic()
    resp = await selected_adapter.forward(body, headers)
    latency_ms = int((time.monotonic() - start) * 1000)

    cost = compute_cost(resp.model, resp.prompt_tokens, resp.completion_tokens)

    trace = TraceCreate(
        project_id=project.id,
        provider=provider_name,
        model=resp.model,
        latency_ms=latency_ms,
        prompt_tokens=resp.prompt_tokens,
        completion_tokens=resp.completion_tokens,
        cost_usd=cost.total_cost_usd,
        status_code=resp.status_code,
        request_body=body,
        response_body=resp.body,
        error_message=resp.error_message,
        risk_tier=risk_tier,
        session_id=session_id,
    )
    record_trace(trace)

    return JSONResponse(content=resp.body, status_code=resp.status_code)


async def _handle_stream(
    project: Project,
    body: dict,
    headers: dict[str, str],
    selected_adapter: OpenAIAdapter | OpenRouterAdapter,
    provider_name: str,
    risk_tier: str | None = None,
    session_id=None,
) -> StreamingResponse:
    """Process a streaming chat completion request."""
    buffer: list[bytes] = []
    buffer_size = 0
    buffer_capped = False
    start = time.monotonic()

    async def stream_and_capture():  # type: ignore[no-untyped-def]
        nonlocal buffer_size, buffer_capped
        async for chunk in selected_adapter.forward_stream(body, headers):
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
            provider=provider_name,
            model=model,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost.total_cost_usd,
            status_code=200,
            request_body=body,
            response_body=response_body,
            error_message=None,
            risk_tier=risk_tier,
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
