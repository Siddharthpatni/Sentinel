"""Sentinel SDK — Drop-in replacement for OpenAI and Anthropic clients,
plus a programmatic client for the Sentinel control plane."""

from sentinel.client import Anthropic, OpenAI
from sentinel.management import Sentinel, SentinelError
from sentinel.tracing import SpanRecord, Trace, current_span, current_trace, trace

__all__ = [
    "Anthropic",
    "OpenAI",
    "Sentinel",
    "SentinelError",
    "SpanRecord",
    "Trace",
    "current_span",
    "current_trace",
    "trace",
]
