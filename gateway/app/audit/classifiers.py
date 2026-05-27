"""Risk-tier classifier — matches a request body against project rules.

The EU AI Act recognises four risk tiers. Sentinel uses the same names so
external compliance tooling can ingest exports without translation:

  - ``unacceptable`` — prohibited use cases (e.g. social scoring).
  - ``high``         — regulated uses (employment, education, critical infra).
  - ``limited``      — transparency obligations (chatbots, deepfakes).
  - ``minimal``      — everything else.

A classifier is the first enabled rule (ordered by name) whose JSONPath
matches the request. No match ⇒ ``risk_tier`` stays ``None``.
"""

from __future__ import annotations

import logging
from typing import Iterable

from jsonpath_ng.ext import parse as jsonpath_parse

logger = logging.getLogger(__name__)

ALLOWED_TIERS = {"unacceptable", "high", "limited", "minimal"}


def classify(body: dict, classifiers: Iterable) -> str | None:
    """Return the risk_tier of the first matching classifier, or None."""
    for c in classifiers:
        if not getattr(c, "enabled", True):
            continue
        try:
            expr = jsonpath_parse(c.match_jsonpath)
        except Exception:  # noqa: BLE001
            logger.warning("Invalid JSONPath on classifier %s: %r", c.id, c.match_jsonpath)
            continue
        if expr.find(body):
            return c.risk_tier
    return None
