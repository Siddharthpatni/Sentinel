"""Eval YAML schema definitions (pydantic models for the suite file format)."""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class TargetSpec(BaseModel):
    endpoint: str = "/v1/chat/completions"
    model: str


class ContainsAssertion(BaseModel):
    type: Literal["contains", "not_contains"]
    path: str = "$.choices[0].message.content"
    value: str
    case_sensitive: bool = False


class EqualsAssertion(BaseModel):
    type: Literal["equals", "not_equals"]
    path: str = "$.choices[0].message.content"
    value: str | int | float | bool


class RegexAssertion(BaseModel):
    type: Literal["regex"]
    path: str = "$.choices[0].message.content"
    pattern: str


class MaxLatencyAssertion(BaseModel):
    type: Literal["max_latency_ms"]
    value: int = Field(gt=0)


class MaxCostAssertion(BaseModel):
    type: Literal["max_cost_usd"]
    value: float = Field(gt=0)


class LlmJudgeAssertion(BaseModel):
    type: Literal["llm_judge"]
    judge_model: str
    criterion: str
    passing_confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class JsonSchemaAssertion(BaseModel):
    type: Literal["json_schema"]
    schema_: dict = Field(alias="schema")


Assertion = Annotated[
    Union[
        ContainsAssertion,
        EqualsAssertion,
        RegexAssertion,
        MaxLatencyAssertion,
        MaxCostAssertion,
        LlmJudgeAssertion,
        JsonSchemaAssertion,
    ],
    Field(discriminator="type"),
]


class EvalCaseSpec(BaseModel):
    name: str = Field(min_length=1)
    input: dict
    assertions: list[Assertion] = Field(min_length=1)


class EvalSuiteSpec(BaseModel):
    name: str = Field(min_length=1)
    target: TargetSpec
    cases: list[EvalCaseSpec] = Field(min_length=1)


def parse_suite_yaml(text: str) -> EvalSuiteSpec:
    """Parse a YAML string into a validated EvalSuiteSpec."""
    import yaml

    raw = yaml.safe_load(text)
    if not isinstance(raw, dict):
        raise ValueError("YAML root must be a mapping")
    return EvalSuiteSpec.model_validate(raw)
