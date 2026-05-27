"""GitHub Actions entrypoint — run an eval suite against a deployed Sentinel gateway.

Usage (inside a workflow step):

    python -m app.evals.github_action \
        --suite ./evals/customer-support.yaml \
        --gateway-url $SENTINEL_GATEWAY_URL \
        --api-key $SENTINEL_API_KEY \
        --fail-on-regression

The script:
- Parses the YAML suite locally (so syntax errors fail fast before any HTTP).
- POSTs each case to the gateway and runs assertions in-process.
- Emits a markdown summary to ``$GITHUB_STEP_SUMMARY`` (if set) and stdout.
- Exits 0 on full pass, 1 on any failure when ``--fail-on-regression`` is set
  (otherwise always 0 — useful for first-time wiring).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass

import httpx

from app.evals.assertions import CallResult, run_assertion
from app.evals.parser import EvalSuiteSpec, parse_suite_yaml
from app.tracing.cost import compute_cost


@dataclass
class CaseOutcome:
    name: str
    passed: bool
    latency_ms: int
    status_code: int
    assertions: list[dict]


def _call(url: str, body: dict, api_key: str, timeout: float) -> tuple[dict, int, int]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    start = time.monotonic()
    resp = httpx.post(url, json=body, headers=headers, timeout=timeout)
    latency_ms = int((time.monotonic() - start) * 1000)
    try:
        data = resp.json()
    except Exception:  # noqa: BLE001
        data = {"_raw": resp.text}
    return data, latency_ms, resp.status_code


def _cost(response: dict) -> float:
    try:
        usage = response.get("usage") or {}
        return float(
            compute_cost(
                response.get("model", ""),
                int(usage.get("prompt_tokens", 0) or 0),
                int(usage.get("completion_tokens", 0) or 0),
            ).total_cost_usd
        )
    except Exception:  # noqa: BLE001
        return 0.0


def _run(suite: EvalSuiteSpec, gateway_url: str, api_key: str, timeout: float) -> list[CaseOutcome]:
    url = f"{gateway_url.rstrip('/')}{suite.target.endpoint}"
    outcomes: list[CaseOutcome] = []
    for case in suite.cases:
        body = dict(case.input)
        body.setdefault("model", suite.target.model)
        try:
            response, latency_ms, status = _call(url, body, api_key, timeout)
        except Exception as exc:  # noqa: BLE001
            outcomes.append(CaseOutcome(
                name=case.name,
                passed=False,
                latency_ms=0,
                status_code=0,
                assertions=[{"type": "transport", "passed": False, "detail": str(exc)}],
            ))
            continue

        call = CallResult(response=response, latency_ms=latency_ms, cost_usd=_cost(response))
        logs = []
        all_passed = status < 400
        if not all_passed:
            logs.append({"type": "http_status", "passed": False, "detail": f"got {status}"})
        for a in case.assertions:
            r = run_assertion(a, call)
            logs.append(asdict(r))
            if not r.passed:
                all_passed = False
        outcomes.append(CaseOutcome(
            name=case.name,
            passed=all_passed,
            latency_ms=latency_ms,
            status_code=status,
            assertions=logs,
        ))
    return outcomes


def _markdown(suite: EvalSuiteSpec, outcomes: list[CaseOutcome]) -> str:
    total = len(outcomes)
    passed = sum(1 for o in outcomes if o.passed)
    failed = total - passed
    lines = [
        f"# Sentinel eval — `{suite.name}`",
        "",
        f"**{passed}/{total} passed**, {failed} failed",
        "",
        "| case | result | latency | failed assertions |",
        "| --- | --- | --- | --- |",
    ]
    for o in outcomes:
        icon = "✅" if o.passed else "❌"
        fails = [a for a in o.assertions if not a["passed"]]
        fail_text = "—" if not fails else "; ".join(f"`{a['type']}`" for a in fails)
        lines.append(f"| `{o.name}` | {icon} | {o.latency_ms}ms | {fail_text} |")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a Sentinel eval suite in CI.")
    parser.add_argument("--suite", required=True, help="Path to YAML suite")
    parser.add_argument("--gateway-url", required=True, help="Sentinel gateway base URL")
    parser.add_argument("--api-key", default=os.environ.get("SENTINEL_API_KEY", ""))
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--fail-on-regression", action="store_true")
    parser.add_argument("--json", action="store_true", help="Also emit machine-readable JSON")
    args = parser.parse_args(argv)

    if not args.api_key:
        print("error: --api-key (or $SENTINEL_API_KEY) is required", file=sys.stderr)
        return 2

    with open(args.suite) as fh:
        suite = parse_suite_yaml(fh.read())

    outcomes = _run(suite, args.gateway_url, args.api_key, args.timeout)
    md = _markdown(suite, outcomes)
    print(md)

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a") as fh:
            fh.write(md + "\n")

    if args.json:
        print(json.dumps({
            "suite": suite.name,
            "outcomes": [asdict(o) for o in outcomes],
        }, indent=2))

    any_failed = any(not o.passed for o in outcomes)
    if any_failed and args.fail_on_regression:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
