"""Example task contracts for the lean dialectical runtime.

This file is the ONE-CASE-SPECIFIC part of the lean engine. It is written for
the rehearsal's example task (triage one support message into
справка/жалоба/другое and draft a reply) purely as a worked, runnable
reference. On hackathon day, once the real case is known, this is the file
you rewrite first: swap `Draft` for whatever the case's actual output shape
is, and adjust `Fact`/`Chain`/`CheckResult` only if you keep the same
six-stage shape (you usually should -- see graph.py's module docstring).
"""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Draft(StrictModel):
    category: Literal["справка", "жалоба", "другое"]
    reply: str = Field(min_length=1)


class Fact(StrictModel):
    statement: str
    basis: Literal["message", "draft", "inference", "assumption"]


class Chain(StrictModel):
    simplest: str
    development: list[Fact]
    opposites: list[str]
    contradiction: str | None
    leap: str | None


class CheckResult(StrictModel):
    status: Literal["clear", "resolved", "needs_clarification", "inconclusive"]
    draft: Draft
    chain: Chain
    plan: list[str]
    clarification: str | None
    summary: str
