"""Management client for the Sentinel control plane.

Wraps the gateway's REST API (`/api/...`) so developers can manage
verification rules, routing policies, eval suites, and fetch traces from
Python without hand-rolling HTTP. Pairs with :class:`sentinel.OpenAI` /
:class:`sentinel.Anthropic` for the data-plane (proxy) side.

Example::

    from sentinel import Sentinel

    s = Sentinel(url="http://localhost:8000")

    project_id = s.projects.list()[0]["id"]

    # Create a verification rule: re-check every user turn with a judge.
    rule = s.verifications.create_rule(
        project_id=project_id,
        name="user-question-quality",
        match_jsonpath='$.messages[?(@.role == "user")]',
        sample_rate=0.1,
        judge_model="gpt-4o-mini",
        judge_prompt_template=(
            "Did this assistant response answer the user? "
            'Return JSON {"verdict": "agree|disagree|uncertain", '
            '"confidence": 0..1, "reasoning": "..."}.\\n\\n'
            "User: {{ request.messages[-1].content }}\\n"
            "Assistant: {{ response.choices[0].message.content }}"
        ),
    )

    # Trigger an eval suite and wait for the result.
    run = s.evals.run(eval_id)
    print(f"{run['passed']}/{run['total']} passed")
"""

from __future__ import annotations

from typing import Any

import httpx


class SentinelError(RuntimeError):
    """Raised when the gateway returns a non-2xx response."""

    def __init__(self, status_code: int, body: Any) -> None:
        super().__init__(f"Sentinel API error {status_code}: {body}")
        self.status_code = status_code
        self.body = body


class _Resource:
    def __init__(self, client: Sentinel) -> None:
        self._client = client


class _Projects(_Resource):
    def list(self) -> list[dict]:
        return self._client._get("/api/projects")["projects"]


class _Traces(_Resource):
    def list(self, *, limit: int = 50, project_id: str | None = None) -> list[dict]:
        params: dict[str, Any] = {"limit": limit}
        if project_id:
            params["project_id"] = project_id
        return self._client._get("/api/traces", params=params)["traces"]

    def get(self, trace_id: str) -> dict:
        return self._client._get(f"/api/traces/{trace_id}")

    def stats(self) -> dict:
        return self._client._get("/api/traces/stats")


class _Verifications(_Resource):
    def list_rules(self, project_id: str) -> list[dict]:
        return self._client._get(
            "/api/verification-rules", params={"project_id": project_id}
        )["rules"]

    def create_rule(
        self,
        *,
        project_id: str,
        name: str,
        match_jsonpath: str,
        sample_rate: float,
        judge_model: str,
        judge_prompt_template: str,
        enabled: bool = True,
    ) -> dict:
        return self._client._post(
            "/api/verification-rules",
            json={
                "project_id": project_id,
                "name": name,
                "match_jsonpath": match_jsonpath,
                "sample_rate": sample_rate,
                "judge_model": judge_model,
                "judge_prompt_template": judge_prompt_template,
                "enabled": enabled,
            },
        )

    def update_rule(self, rule_id: str, **fields: Any) -> dict:
        return self._client._patch(f"/api/verification-rules/{rule_id}", json=fields)

    def delete_rule(self, rule_id: str) -> None:
        self._client._delete(f"/api/verification-rules/{rule_id}")

    def list(
        self,
        *,
        trace_id: str | None = None,
        verdict: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        params: dict[str, Any] = {"limit": limit}
        if trace_id:
            params["trace_id"] = trace_id
        if verdict:
            params["verdict"] = verdict
        return self._client._get("/api/verifications", params=params)["verifications"]


class _RoutingPolicies(_Resource):
    def list(self, project_id: str) -> list[dict]:
        return self._client._get(
            "/api/routing-policies", params={"project_id": project_id}
        )["policies"]

    def create(
        self,
        *,
        project_id: str,
        name: str,
        match_jsonpath: str,
        candidates: list[dict],
        fallback_on: dict | None = None,
        enabled: bool = True,
    ) -> dict:
        return self._client._post(
            "/api/routing-policies",
            json={
                "project_id": project_id,
                "name": name,
                "match_jsonpath": match_jsonpath,
                "candidates": candidates,
                "fallback_on": fallback_on or {"http_5xx": True},
                "enabled": enabled,
            },
        )

    def update(self, policy_id: str, **fields: Any) -> dict:
        return self._client._patch(f"/api/routing-policies/{policy_id}", json=fields)

    def delete(self, policy_id: str) -> None:
        self._client._delete(f"/api/routing-policies/{policy_id}")


class _Evals(_Resource):
    def list(self, project_id: str | None = None) -> list[dict]:
        params = {"project_id": project_id} if project_id else None
        return self._client._get("/api/evals", params=params)["evals"]

    def create(self, *, project_id: str, yaml_source: str) -> dict:
        return self._client._post(
            "/api/evals", json={"project_id": project_id, "yaml_source": yaml_source}
        )

    def delete(self, eval_id: str) -> None:
        self._client._delete(f"/api/evals/{eval_id}")

    def run(
        self,
        eval_id: str,
        *,
        triggered_by: str = "sdk",
        git_sha: str | None = None,
    ) -> dict:
        """Trigger a suite run. Blocks until the suite finishes."""
        return self._client._post(
            f"/api/evals/{eval_id}/run",
            json={"triggered_by": triggered_by, "git_sha": git_sha},
        )

    def runs(self, eval_id: str, *, limit: int = 50) -> list[dict]:
        return self._client._get(
            f"/api/evals/{eval_id}/runs", params={"limit": limit}
        )["runs"]

    def run_detail(self, eval_id: str, run_id: str) -> dict:
        return self._client._get(f"/api/evals/{eval_id}/runs/{run_id}")


class _Audit(_Resource):
    """EU AI Act audit module — risk-tier classifiers + tamper-evident ledger."""

    def list_classifiers(self, project_id: str | None = None) -> list[dict]:
        params = {"project_id": project_id} if project_id else None
        return self._client._get("/api/audit/classifiers", params=params)["classifiers"]

    def create_classifier(
        self,
        *,
        project_id: str,
        name: str,
        match_jsonpath: str,
        risk_tier: str,
        enabled: bool = True,
    ) -> dict:
        return self._client._post(
            "/api/audit/classifiers",
            json={
                "project_id": project_id,
                "name": name,
                "match_jsonpath": match_jsonpath,
                "risk_tier": risk_tier,
                "enabled": enabled,
            },
        )

    def update_classifier(self, classifier_id: str, **fields: Any) -> dict:
        return self._client._patch(
            f"/api/audit/classifiers/{classifier_id}", json=fields
        )

    def delete_classifier(self, classifier_id: str) -> None:
        self._client._delete(f"/api/audit/classifiers/{classifier_id}")

    def export(
        self,
        *,
        project_id: str,
        since: str | None = None,
        until: str | None = None,
        risk_tier: str | None = None,
    ) -> list[dict]:
        """Pull the audit ledger as a list of dicts (one per entry).

        For large exports prefer streaming the NDJSON endpoint directly with
        ``httpx`` — this helper buffers everything in memory.
        """
        params: dict[str, Any] = {"project_id": project_id}
        if since:
            params["since"] = since
        if until:
            params["until"] = until
        if risk_tier:
            params["risk_tier"] = risk_tier
        resp = self._client._http.get("/api/audit/export", params=params)
        if resp.status_code >= 400:
            raise SentinelError(resp.status_code, resp.text)
        import json
        return [json.loads(line) for line in resp.text.splitlines() if line.strip()]

    def verify(self, project_id: str) -> dict:
        return self._client._get("/api/audit/verify", params={"project_id": project_id})


class _Alerts(_Resource):
    """Threshold alerts on cost / error-rate / p95-latency over a rolling window."""

    def list(self, project_id: str | None = None) -> list[dict]:
        params = {"project_id": project_id} if project_id else None
        return self._client._get("/api/alerts", params=params)["alerts"]

    def create(
        self,
        *,
        project_id: str,
        name: str,
        metric: str,
        threshold: float,
        comparator: str = "gt",
        window_minutes: int = 60,
        enabled: bool = True,
    ) -> dict:
        return self._client._post(
            "/api/alerts",
            json={
                "project_id": project_id,
                "name": name,
                "metric": metric,
                "threshold": threshold,
                "comparator": comparator,
                "window_minutes": window_minutes,
                "enabled": enabled,
            },
        )

    def update(self, alert_id: str, **fields: Any) -> dict:
        return self._client._patch(f"/api/alerts/{alert_id}", json=fields)

    def delete(self, alert_id: str) -> None:
        self._client._delete(f"/api/alerts/{alert_id}")

    def check(self, alert_id: str) -> dict:
        """Evaluate the alert now and persist the result on the row."""
        return self._client._post(f"/api/alerts/{alert_id}/check", json={})


class _Annotations(_Resource):
    """Human feedback on traces — LangSmith-style ratings + comments."""

    def create(
        self,
        *,
        trace_id: str,
        rating: str,
        dimension: str = "overall",
        comment: str | None = None,
        author: str | None = None,
    ) -> dict:
        return self._client._post(
            "/api/annotations",
            json={
                "trace_id": trace_id,
                "rating": rating,
                "dimension": dimension,
                "comment": comment,
                "author": author,
            },
        )

    def list(
        self,
        *,
        trace_id: str | None = None,
        rating: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        params: dict[str, Any] = {"limit": limit}
        if trace_id:
            params["trace_id"] = trace_id
        if rating:
            params["rating"] = rating
        return self._client._get("/api/annotations", params=params)["annotations"]

    def delete(self, annotation_id: str) -> None:
        self._client._delete(f"/api/annotations/{annotation_id}")


class _Sessions(_Resource):
    """Conversation threads — group traces by an external session ID.

    To stamp a trace with a session, pass ``extra_body={"_sentinel":
    {"session_id": "...", "session_name": "..."}}`` when you call
    ``client.chat.completions.create(...)`` against the proxy.
    """

    def list(self, *, project_id: str | None = None, limit: int = 50) -> list[dict]:
        params: dict[str, Any] = {"limit": limit}
        if project_id:
            params["project_id"] = project_id
        return self._client._get("/api/sessions", params=params)["sessions"]

    def get(self, session_id: str) -> dict:
        return self._client._get(f"/api/sessions/{session_id}")

    def delete(self, session_id: str) -> None:
        self._client._delete(f"/api/sessions/{session_id}")


class Sentinel:
    """Programmatic access to a Sentinel gateway's control plane.

    Args:
        url: Base URL of the Sentinel gateway (e.g. ``http://localhost:8000``).
        api_key: Project API key. Optional for read endpoints, recommended
            otherwise.
        timeout: HTTP timeout in seconds.
    """

    def __init__(
        self,
        *,
        url: str = "http://localhost:8000",
        api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._url = url.rstrip("/")
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._http = httpx.Client(base_url=self._url, headers=headers, timeout=timeout)

        self.projects = _Projects(self)
        self.traces = _Traces(self)
        self.verifications = _Verifications(self)
        self.routing = _RoutingPolicies(self)
        self.evals = _Evals(self)
        self.audit = _Audit(self)
        self.alerts = _Alerts(self)
        self.annotations = _Annotations(self)
        self.sessions = _Sessions(self)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Sentinel:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        resp = self._http.request(method, path, **kwargs)
        if resp.status_code == 204:
            return None
        try:
            data = resp.json()
        except Exception:  # noqa: BLE001
            data = resp.text
        if resp.status_code >= 400:
            raise SentinelError(resp.status_code, data)
        return data

    def _get(self, path: str, *, params: dict | None = None) -> Any:
        return self._request("GET", path, params=params)

    def _post(self, path: str, *, json: dict) -> Any:
        return self._request("POST", path, json=json)

    def _patch(self, path: str, *, json: dict) -> Any:
        return self._request("PATCH", path, json=json)

    def _delete(self, path: str) -> None:
        self._request("DELETE", path)
