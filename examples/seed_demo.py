"""Seed a freshly-started Sentinel instance with demo data.

What you get
------------
- ~12 chat traces against gpt-4o-mini (varied prompts, two sessions, one
  intentional error so the error-rate stat is non-zero)
- a 4-span agent trace via `sentinel.trace()` so the waterfall on
  /traces/<id> has something to show
- a routing policy, a verification rule, and a dataset (with one item)

Total OpenAI cost: well under $0.01.

Prereqs
-------
    docker compose up -d              # gateway+dashboard+postgres+redis
    export OPENAI_API_KEY=sk-...      # any real OpenAI key
    pip install -e ./sdk

Run
---
    python examples/seed_demo.py

Then open http://localhost:3000.
"""

from __future__ import annotations

import os
import random
import sys
import time
import uuid

from sentinel import OpenAI, Sentinel, trace

GATEWAY = os.environ.get("SENTINEL_URL", "http://localhost:8000")
API_KEY = os.environ.get("SENTINEL_API_KEY", "sk-sentinel-dev-000")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY")

PROMPTS = [
    ("You are a terse assistant.", "What is 2+2?"),
    ("You are a haiku poet.", "Write a haiku about observability."),
    ("You are a SQL tutor.", "Explain INNER JOIN in one sentence."),
    ("You are a translator.", "Translate 'hello world' to French."),
    ("You are a fact-checker.", "Is the sky blue? Yes or no."),
    ("You are a code reviewer.", "What's wrong with `if x = 5:` in Python?"),
    ("You are a chef.", "What's a good substitute for buttermilk?"),
    ("You are a historian.", "When did WWII end?"),
]

SESSION_A = f"chat-session-{uuid.uuid4().hex[:8]}"
SESSION_B = f"chat-session-{uuid.uuid4().hex[:8]}"


def need_openai_key() -> None:
    if OPENAI_KEY:
        return
    sys.stderr.write(
        "ERROR: OPENAI_API_KEY not set. The seed script makes real (cheap)\n"
        "OpenAI calls to populate the dashboard. Export your key and rerun:\n\n"
        "    export OPENAI_API_KEY=sk-...\n"
        "    python examples/seed_demo.py\n",
    )
    sys.exit(2)


def fire_chat_traces(client: OpenAI) -> None:
    print("→ firing 8 varied chat completions...")
    for i, (system, user) in enumerate(PROMPTS):
        session_id = SESSION_A if i < 4 else SESSION_B
        try:
            client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.2,
                max_tokens=80,
                extra_body={"_sentinel": {"session_id": session_id}},
            )
            print(f"   [{i + 1}/8] ok  · session={session_id[:18]}")
        except Exception as exc:
            print(f"   [{i + 1}/8] err · {exc}")
        time.sleep(random.uniform(0.1, 0.4))

    print("→ firing one intentional error (bad model name)...")
    try:
        client.chat.completions.create(
            model="gpt-this-model-does-not-exist",
            messages=[{"role": "user", "content": "hello"}],
            max_tokens=10,
        )
    except Exception as exc:
        print(f"   ok, error captured: {type(exc).__name__}")


def fire_agent_span_tree(client: OpenAI) -> None:
    print("→ emitting agent span tree...")
    with trace(
        "demo_research_agent",
        sentinel_url=GATEWAY,
        sentinel_api_key=API_KEY,
    ) as t:
        topics = ["postgres indexes", "redis pub/sub"]
        for topic in topics:
            with t.span("plan", span_type="tool", topic=topic) as plan:
                plan.set_attribute("strategy", "single-shot")
            with t.span("summarize", span_type="llm", model="gpt-4o-mini"):
                client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "Summarize in one sentence."},
                        {"role": "user", "content": f"Explain {topic} to a junior dev."},
                    ],
                    max_tokens=60,
                )
        print(f"   trace id: {t.id}")
        print(f"   open: {GATEWAY.replace(':8000', ':3000')}/traces/{t.id}")


def seed_control_plane(s: Sentinel, project_id: str) -> None:
    print("→ creating a routing policy...")
    try:
        s.routing.create(
            project_id=project_id,
            name="demo-cheap-first",
            match_jsonpath="$.model[?(@ == 'gpt-4o')]",
            candidates=[{"model": "gpt-4o-mini"}, {"model": "gpt-4o"}],
        )
        print("   ok")
    except Exception as exc:
        print(f"   skipped: {exc}")

    print("→ creating a verification rule...")
    try:
        s.verifications.create_rule(
            project_id=project_id,
            name="demo-agreement-judge",
            match_jsonpath='$.messages[?(@.role == "user")]',
            sample_rate=0.2,
            judge_model="gpt-4o-mini",
            judge_prompt_template=(
                'Return JSON {"verdict": "agree|disagree|uncertain", '
                '"confidence": 0..1, "reasoning": "short"}.\n\n'
                "User: {{ request.messages[-1].content }}\n"
                "Assistant: {{ response.choices[0].message.content }}"
            ),
        )
        print("   ok")
    except Exception as exc:
        print(f"   skipped: {exc}")

    print("→ creating a demo dataset...")
    try:
        ds = s._post(
            "/api/datasets",
            json={
                "project_id": project_id,
                "name": "demo-arithmetic",
                "description": "A handful of basic-arithmetic prompts for replay.",
            },
        )
        s._post(
            f"/api/datasets/{ds['id']}/items",
            json={
                "input": {
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": "What is 2+2?"}],
                },
                "expected_output": {"content": "4"},
            },
        )
        print(f"   ok · {ds['id']}")
    except Exception as exc:
        print(f"   skipped: {exc}")


def main() -> None:
    need_openai_key()

    print(f"\nSeeding demo data into {GATEWAY}\n")

    s = Sentinel(url=GATEWAY, api_key=API_KEY)
    projects = s.projects.list()
    if not projects:
        sys.exit("No projects found — is the gateway running?")
    project = projects[0]
    project_id = project["id"]
    print(f"using project: {project['name']} ({project_id})\n")

    client = OpenAI(
        sentinel_url=GATEWAY,
        sentinel_api_key=API_KEY,
        provider_api_key=OPENAI_KEY,
    )

    fire_chat_traces(client)
    print()
    fire_agent_span_tree(client)
    print()
    seed_control_plane(s, project_id)

    s.close()
    print(
        "\ndone — open http://localhost:3000 to explore the seeded traces,\n"
        "sessions, datasets, routing policy, and verification rule.\n",
    )


if __name__ == "__main__":
    main()
