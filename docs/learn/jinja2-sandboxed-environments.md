# Jinja2 sandboxed environments

Sentinel renders verification judge prompts from user-controlled templates.
Templates are stored in the database (`verification_rules.judge_prompt_template`)
and rendered with the request/response payload as context. That's a server-side
template injection vulnerability waiting to happen — `{{ "".__class__.__mro__ }}`
in a vanilla Jinja2 environment leaks the entire Python type hierarchy.

## SandboxedEnvironment

```python
from jinja2.sandbox import SandboxedEnvironment
env = SandboxedEnvironment()
template = env.from_string(user_template)
template.render(request=req, response=resp)
```

The sandbox blocks access to attributes starting with `_` and to a curated
denylist of "unsafe" methods. Accessing `__class__` raises `SecurityError`.

## What it does NOT do
- Limit render time or memory. Pair with a timeout when rendering on a hot
  path.
- Prevent CPU-burn templates (deeply nested loops). Sentinel sidesteps this
  by running renders inside a Celery task with a per-call ceiling.
- Stop logical exfiltration — if you pass secrets into the render context,
  the template can dump them. Only pass what the template needs.
