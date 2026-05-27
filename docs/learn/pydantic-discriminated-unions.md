# Pydantic discriminated unions

Eval suites support seven assertion types: `contains`, `equals`, `regex`,
`max_latency_ms`, `max_cost_usd`, `llm_judge`, `json_schema`. Each has a
different field shape. We need pydantic to parse a list of mixed
assertions from YAML and validate each by its `type`.

## The pattern

```python
from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field

class ContainsAssertion(BaseModel):
    type: Literal["contains", "not_contains"]
    path: str
    value: str

class RegexAssertion(BaseModel):
    type: Literal["regex"]
    pattern: str

Assertion = Annotated[
    Union[ContainsAssertion, RegexAssertion],
    Field(discriminator="type"),
]
```

`discriminator="type"` tells pydantic to inspect the `type` field first,
then dispatch to the right model. Without it, pydantic would try every
variant in order and pick the first that succeeds — slow and error-prone.

## Mutually-exclusive fields

You can't put `path` (required for `contains`) and `pattern` (required for
`regex`) on the same model with optional types — pydantic would happily
accept a `contains` assertion missing `path`. Discriminated unions enforce
the per-variant shape.

## YAML interop

`yaml.safe_load(text)` returns a `dict[str, Any]`. Feed it straight into
`EvalSuiteSpec.model_validate(raw)` and pydantic resolves the discriminator
on the assertion list.
