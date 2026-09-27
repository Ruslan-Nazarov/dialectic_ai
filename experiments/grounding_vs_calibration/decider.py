"""Decider interface matched to Jev's Choice primitive: choice(state, options) -> {choice, probabilities, confidence}.

Two implementations:
- SurrogateDecider: a real logprob-supporting non-reasoning chat model. Swap the model via config.
- JevDecider: calls TypeSafe's real Jev model via POST /v1/systemone with a `choice` question,
  per https://docs.typesafe.ai/api.md and https://docs.typesafe.ai/primitives/choice.md.
  Requires TYPESAFE_API_KEY (loaded from .env by the calling script).
"""
from __future__ import annotations

import json
import math
import os
import urllib.request
from dataclasses import dataclass
from typing import Protocol


@dataclass
class ChoiceResult:
    choice: str
    probabilities: dict[str, float]
    confidence: float  # probability mass on the top choice
    prompt_tokens: int = 0
    completion_tokens: int = 0


class Decider(Protocol):
    def choice(self, state: str, options: list[str]) -> ChoiceResult: ...


def supports_logprobs(model: str, base_url: str, api_key_env: str) -> bool:
    """Empirically check whether `model` returns logprobs and accepts temperature.

    Reasoning models (gpt-5, o-series) are expected to reject/ignore both; verify, don't assume.
    """
    api_key = os.environ.get(api_key_env, "")
    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": "Say 'ok'."}],
            "max_tokens": 5,
            "temperature": 0.0,
            "logprobs": True,
            "top_logprobs": 5,
        }
    ).encode()
    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        return False
    choice = data.get("choices", [{}])[0]
    lp = choice.get("logprobs")
    return bool(lp and lp.get("content"))


class SurrogateDecider:
    """Real non-reasoning chat model with logprobs, used to estimate a Choice-with-probabilities distribution."""

    def __init__(self, model: str, base_url: str, api_key_env: str):
        self.model = model
        self.base_url = base_url
        self.api_key = os.environ.get(api_key_env, "")

    def choice(self, state: str, options: list[str]) -> ChoiceResult:
        if len(options) > 26:
            raise ValueError(
                f"{len(options)} options exceed the 26-letter single-token labeling scheme; "
                "use choice_binary_none() instead for large option sets."
            )
        labels = [chr(ord("A") + i) for i in range(len(options))]
        option_lines = "\n".join(f"{lab}. {opt}" for lab, opt in zip(labels, options))
        prompt = (
            f"{state}\n\nWhich option applies? Answer with a single letter only.\n{option_lines}"
        )
        body = json.dumps(
            {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1,
                "temperature": 0.0,
                "logprobs": True,
                "top_logprobs": 20,
            }
        ).encode()
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        choice_obj = data["choices"][0]
        top_logprobs = choice_obj["logprobs"]["content"][0]["top_logprobs"]

        raw = {}
        for entry in top_logprobs:
            tok = entry["token"].strip().upper()
            if tok in labels:
                raw[tok] = raw.get(tok, 0.0) + math.exp(entry["logprob"])
        total = sum(raw.values())
        if total == 0:
            probs = {opt: 1.0 / len(options) for opt in options}
        else:
            probs = {opt: raw.get(lab, 0.0) / total for lab, opt in zip(labels, options)}

        best_opt = max(probs, key=probs.get)
        return ChoiceResult(
            choice=best_opt,
            probabilities=probs,
            confidence=probs[best_opt],
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    def choice_world_brief(self, state: str, brief_text: str) -> ChoiceResult:
        """Binary Choice against the world description the agent itself saw, not an exhaustive
        list of all 152 processes. See PREREGISTRATION.md amendment dated 2026-09-27 ("variant 2
        list-content correction, round 2"): the world has 152 active processes, but the agent
        that produced the answers being scored only ever saw `WorldAdapter.brief()` (max_chars
        =8000, `data.world_brief()`) -- the same size-limited excerpt used to build eval_v3.py's
        system prompt. Asking about all 152 processes asks about processes the agent never had
        access to; asking about the brief keeps variant 2 in the same condition as variant 1
        (self-report) and as the agent's own run. Forces a single-token binary answer -- 'M'
        (matches something in the brief) or 'N' (none fits) -- so the model's one-token output
        stays inside a valid, always-representable label space (SurrogateDecider's logprob
        scheme cannot use free-form multi-way Choice the way JevDecider can).
        """
        prompt = (
            f"{state}\n\nWorld description (as given to the agent):\n{brief_text}\n\n"
            "Does this answer's reasoning engage ANY of the processes described above (M), "
            "or NONE of them (N)? Answer with a single letter only: M or N."
        )
        body = json.dumps(
            {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1,
                "temperature": 0.0,
                "logprobs": True,
                "top_logprobs": 20,
            }
        ).encode()
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        top_logprobs = data["choices"][0]["logprobs"]["content"][0]["top_logprobs"]

        raw = {"M": 0.0, "N": 0.0}
        for entry in top_logprobs:
            tok = entry["token"].strip().upper()
            if tok in raw:
                raw[tok] += math.exp(entry["logprob"])
        total = raw["M"] + raw["N"]
        if total == 0:
            probs = {"some process fits": 0.5, "none fits": 0.5}
        else:
            probs = {"some process fits": raw["M"] / total, "none fits": raw["N"] / total}
        best_opt = max(probs, key=probs.get)
        return ChoiceResult(
            choice=best_opt,
            probabilities=probs,
            confidence=probs[best_opt],
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )


def build_decider(
    surrogate_model: str = "gpt-4o-mini",
    surrogate_base_url: str = "https://api.openai.com/v1",
    surrogate_api_key_env: str = "OPENAI_API_KEY",
) -> Decider:
    """One switch for which Decider implementation runs: the `DECIDER_IMPL` env var.

    DECIDER_IMPL=surrogate (default) -> SurrogateDecider on a real logprob-capable model.
    DECIDER_IMPL=jev                 -> JevDecider, calling TypeSafe's Jev model directly.
                                         Requires TYPESAFE_API_KEY.
    """
    impl = os.environ.get("DECIDER_IMPL", "surrogate").strip().lower()
    if impl == "jev":
        return JevDecider()
    if impl == "surrogate":
        return SurrogateDecider(surrogate_model, surrogate_base_url, surrogate_api_key_env)
    raise ValueError(f"unknown DECIDER_IMPL={impl!r}; expected 'surrogate' or 'jev'")


class JevDecider:
    """Calls TypeSafe's real Jev model (POST /v1/systemone) with a single `choice` question,
    per https://docs.typesafe.ai/api.md and https://docs.typesafe.ai/primitives/choice.md.

    Request: {"state": ..., "model": "jev-latest", "questions": {"<qid>": {"type": "choice",
    "instructions": ..., "criteria": {<key>: <description-or-null>, ...}}}}.
    Response: {"answers": {"<qid>": {"type": "choice", "choice": <key>,
    "probabilities": {<key>: p, ...}, "confidence": p}}, "usage": {"input_tokens": n,
    "output_tokens": n}}.

    The Choice primitive supports up to 255 options per question (confirmed against the live
    docs) -- no 26-option single-token ceiling the way SurrogateDecider's logprob scheme has.
    But a *content* limit was found empirically: 64k tokens per request, 32k for `state` plus
    the longest question (TypeSafe's Models page) -- a full 152-process list with real
    formulations (not bare ids) exceeds that (`max_tokens_exceeded`, confirmed live). So variant
    2 (2a/2b/2c) asks about the world-brief text the agent itself saw
    (`data.world_brief()`, ~3.2k tokens), not an exhaustive process list: `choice_world_brief()`
    for the primary 2b-vs-2a binary comparison, `choice_brief_processes()` for the auxiliary,
    exploratory 2c (multi-way Choice among the brief's own ~11 mentioned processes). See
    PREREGISTRATION.md amendment dated 2026-09-27, round 2.
    """

    def __init__(
        self,
        api_key_env: str = "TYPESAFE_API_KEY",
        base_url: str = "https://api.typesafe.ai",
        model: str = "jev-latest",
    ):
        self.api_key = os.environ.get(api_key_env, "")
        self.base_url = base_url
        self.model = model

    def _ask_choice(self, state: str, criteria: dict[str, str | None], instructions: str) -> tuple[dict, dict]:
        body = json.dumps(
            {
                "state": state,
                "model": self.model,
                "questions": {
                    "q": {
                        "type": "choice",
                        "instructions": instructions,
                        "criteria": criteria,
                    }
                },
            }
        ).encode()
        req = urllib.request.Request(
            f"{self.base_url}/v1/systemone",
            data=body,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        return data["answers"]["q"], data.get("usage", {})

    def choice(self, state: str, options: list[str]) -> ChoiceResult:
        if len(options) > 255:
            raise ValueError(f"{len(options)} options exceed Jev's 255-option Choice limit")
        keys = [f"opt_{i}" for i in range(len(options))]
        criteria = dict(zip(keys, options))
        answer, usage = self._ask_choice(
            state, criteria, instructions="Which option applies given the state?"
        )
        key_to_opt = dict(zip(keys, options))
        probs = {key_to_opt[k]: p for k, p in answer["probabilities"].items()}
        return ChoiceResult(
            choice=key_to_opt[answer["choice"]],
            probabilities=probs,
            confidence=answer["confidence"],
            prompt_tokens=usage.get("input_tokens", 0),
            completion_tokens=usage.get("output_tokens", 0),
        )

    def choice_world_brief(self, state: str, brief_text: str) -> ChoiceResult:
        """Primary variant 2b question: identical binary question to
        SurrogateDecider.choice_world_brief() (same wording, same world-brief text -- the
        excerpt the agent itself saw, not an exhaustive 152-process list; see
        PREREGISTRATION.md amendment dated 2026-09-27, round 2), asked via Jev's real `choice`
        primitive with two options ("some" / "none") instead of a single-token logprob hack.
        This keeps 2a and 2b comparable on the same question -- only the model differs.
        probabilities/confidence report P(some) vs P(none fits); `choice` is 'none fits' or
        'some process fits' (not a specific process id), matching SurrogateDecider's contract.

        Also fixes a real API constraint found while building this: a full-152-process listing
        (with each process's actual formulation, not just its bare id) exceeds Jev's documented
        per-request limit (64k tokens total / 32k for `state` plus the longest question) --
        confirmed empirically via a `max_tokens_exceeded` 400 response, not assumed from docs.
        The brief (max_chars=8000, ~3.2k tokens) is well inside that limit.
        """
        instructions = (
            f"World description (as given to the agent):\n{brief_text}\n\n"
            "Does this answer's reasoning engage ANY of the processes described above, "
            "or NONE of them?"
        )
        criteria = {
            "some": "The answer's reasoning engages some of the processes described above.",
            "none": "The answer's reasoning engages none of the processes described above.",
        }
        answer, usage = self._ask_choice(state, criteria, instructions=instructions)
        label_to_opt = {"some": "some process fits", "none": "none fits"}
        probs = {label_to_opt[k]: p for k, p in answer["probabilities"].items()}
        return ChoiceResult(
            choice=label_to_opt[answer["choice"]],
            probabilities=probs,
            confidence=answer["confidence"],
            prompt_tokens=usage.get("input_tokens", 0),
            completion_tokens=usage.get("output_tokens", 0),
        )

    def choice_brief_processes(self, state: str, brief_text: str, id_to_line: dict[str, str]) -> ChoiceResult:
        """Auxiliary, exploratory variant 2c: real multi-way Choice among the processes actually
        mentioned in the world brief (`data.brief_process_descriptions()`, each already carrying
        its own id + formulation), plus "none fits". Unlike the old, abandoned 2c design (all 152
        processes), this option set is small (~11 processes for the NDA world) since the brief
        itself is size-limited -- so no token-limit issue, and the options are exactly what the
        agent could have been referring to. Not part of the primary 2b-vs-2a comparison.
        """
        keys = list(id_to_line.keys()) + ["none"]
        criteria: dict[str, str | None] = dict(id_to_line)
        criteria["none"] = "None of the processes described in the brief are engaged by this answer's reasoning."
        instructions = (
            f"World description (as given to the agent):\n{brief_text}\n\n"
            "Which of the processes described above (identified by id) does this answer's "
            "reasoning engage, if any?"
        )
        answer, usage = self._ask_choice(state, criteria, instructions=instructions)
        opt_to_label = {**id_to_line, "none": "none fits"}
        probs = {opt_to_label[k]: p for k, p in answer["probabilities"].items()}
        return ChoiceResult(
            choice=opt_to_label[answer["choice"]],
            probabilities=probs,
            confidence=answer["confidence"],
            prompt_tokens=usage.get("input_tokens", 0),
            completion_tokens=usage.get("output_tokens", 0),
        )
