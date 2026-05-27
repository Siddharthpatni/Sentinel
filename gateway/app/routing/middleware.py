"""Routing middleware — match request → override model → fall back on failure.

Spec constraints honoured:
- Maximum 3 fallback attempts per request (hard-coded).
- Streaming requests bypass fallback after the first chunk (the gateway
  layer enforces this — middleware only intercepts non-streaming here).
- Routing is opt-in: no policies for the project ⇒ no routing applied.
- Each attempt is its own trace; the per-attempt provenance is stored on
  ``request_body._sentinel.route``.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from jsonpath_ng.ext import parse as jsonpath_parse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RoutingPolicy

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3


@dataclass
class RoutedRequest:
    body: dict
    policy_name: str | None
    candidates_remaining: list[dict]
    parent_request_id: str


async def select_route(
    session: AsyncSession,
    project_id: uuid.UUID,
    body: dict,
) -> RoutedRequest:
    """Pick the first enabled policy whose JSONPath matches the request body.

    If no policy matches, returns a RoutedRequest with the body unchanged
    and an empty candidate list — the caller falls through to standard
    Phase 1 behaviour.
    """
    result = await session.execute(
        select(RoutingPolicy).where(
            RoutingPolicy.project_id == project_id,
            RoutingPolicy.enabled.is_(True),
        )
    )
    policies = result.scalars().all()

    matched: RoutingPolicy | None = None
    for p in policies:
        try:
            expr = jsonpath_parse(p.match_jsonpath)
        except Exception:  # noqa: BLE001
            logger.warning("Invalid JSONPath on policy %s: %r", p.id, p.match_jsonpath)
            continue
        if expr.find(body):
            matched = p
            break

    parent_id = str(uuid.uuid4())
    if matched is None:
        return RoutedRequest(
            body=body, policy_name=None, candidates_remaining=[], parent_request_id=parent_id
        )

    candidates = list(matched.candidates)[:MAX_ATTEMPTS]
    return RoutedRequest(
        body=body,
        policy_name=matched.name,
        candidates_remaining=candidates,
        parent_request_id=parent_id,
    )


def apply_candidate(body: dict, route: RoutedRequest, attempt: int) -> dict:
    """Rewrite request body to use the next candidate model, and stamp provenance."""
    if not route.candidates_remaining:
        return body
    candidate = route.candidates_remaining[0]
    original_model = body.get("model")
    new_body = {**body, "model": candidate["model"]}
    sentinel = dict(body.get("_sentinel", {}))
    sentinel["route"] = {
        "policy": route.policy_name,
        "attempt": attempt,
        "original_model": original_model,
        "parent_request_id": route.parent_request_id,
    }
    new_body["_sentinel"] = sentinel
    return new_body


def should_fall_back(status_code: int, fallback_on: dict) -> bool:
    if status_code >= 500 and fallback_on.get("http_5xx", True):
        return True
    return False


def consume_candidate(route: RoutedRequest) -> None:
    if route.candidates_remaining:
        route.candidates_remaining.pop(0)
