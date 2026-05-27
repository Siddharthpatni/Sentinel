"""Programmatic example: use the Sentinel SDK from any Python project.

This script:
  1. Connects to a running Sentinel gateway.
  2. Lists projects, traces, and verifications.
  3. Creates a routing policy and a verification rule.
  4. Uploads + runs an eval suite, prints the results.

Run: python examples/sdk_quickstart.py
"""

from __future__ import annotations

from sentinel import OpenAI, Sentinel

GATEWAY = "http://localhost:8000"
API_KEY = "sk-sentinel-dev-000"


def main() -> None:
    s = Sentinel(url=GATEWAY, api_key=API_KEY)

    project = s.projects.list()[0]
    print(f"Using project: {project['name']} ({project['id']})")

    print(f"Recent traces: {len(s.traces.list(limit=5))}")
    print(f"Stats: {s.traces.stats()}")

    policy = s.routing.create(
        project_id=project["id"],
        name="cheap-first-fallback",
        match_jsonpath="$.model[?(@ == 'gpt-4o')]",
        candidates=[
            {"model": "gpt-4o-mini"},
            {"model": "gpt-4o"},
        ],
    )
    print(f"Created policy {policy['id']}")

    rule = s.verifications.create_rule(
        project_id=project["id"],
        name="sdk-demo-rule",
        match_jsonpath='$.messages[?(@.role == "user")]',
        sample_rate=1.0,
        judge_model="gpt-4o-mini",
        judge_prompt_template=(
            'Return JSON {"verdict": "agree|disagree|uncertain", '
            '"confidence": 0..1, "reasoning": "short"}.\n\n'
            "User: {{ request.messages[-1].content }}\n"
            "Assistant: {{ response.choices[0].message.content }}"
        ),
    )
    print(f"Created rule {rule['id']}")

    client = OpenAI(sentinel_api_key=API_KEY, sentinel_url=GATEWAY)
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "What is 2+2? Answer in one word."}],
    )
    print(f"Proxied response: {resp.choices[0].message.content}")

    yaml_source = """
name: sdk-demo-suite
target:
  endpoint: /v1/chat/completions
  model: gpt-4o-mini
cases:
  - name: arithmetic
    input:
      messages:
        - role: user
          content: What is 2+2? Answer with just a digit.
    assertions:
      - type: contains
        path: $.choices[0].message.content
        value: "4"
      - type: max_latency_ms
        value: 10000
"""
    suite = s.evals.create(project_id=project["id"], yaml_source=yaml_source)
    run = s.evals.run(suite["id"], triggered_by="sdk-example")
    print(f"Eval run: {run['passed']}/{run['total']} passed")

    s.close()


if __name__ == "__main__":
    main()
