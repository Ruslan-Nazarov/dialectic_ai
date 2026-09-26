"""Decider interface matched to Jev's Choice primitive: choice(state, options) -> {choice, probabilities, confidence}.

Two implementations:
- SurrogateDecider: a real logprob-supporting non-reasoning chat model. Swap the model via config.
- JevDecider: written from TypeSafe AI's public docs for POST /v1/systemone. UNTESTED: NO ACCESS KEY.
  Never call this in this experiment; it exists only so the swap is a one-line config change later.
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

    def choice_binary_none(self, state: str, process_options: list[str]) -> ChoiceResult:
        """For option sets too large for single-letter labeling (>26): list all process ids as
        context, but force a single-token binary answer -- 'M' (matches some listed process) or
        'N' (none fits) -- so the token the model actually produces stays inside a valid,
        always-representable label space. probabilities/confidence report P(some) vs P(none fits);
        `choice` is 'none fits' or 'some process fits' (not a specific process id -- this method
        trades "which process" for a reliable P(none fits), which is the only score this
        experiment's frozen metric needs).
        """
        listed = "\n".join(f"- {p}" for p in process_options)
        prompt = (
            f"{state}\n\nWorld processes:\n{listed}\n\n"
            "Does this answer's reasoning engage ANY of the processes listed above (M), "
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


class JevDecider:
    """UNTESTED: NO ACCESS KEY. Written from TypeSafe AI's public docs for POST /v1/systemone.

    Do not call in this experiment. Kept only so swapping the Decider implementation is one config line.
    """

    def __init__(self, api_key_env: str = "TYPESAFE_API_KEY", base_url: str = "https://api.typesafe.ai"):
        self.api_key = os.environ.get(api_key_env, "")
        self.base_url = base_url

    def choice(self, state: str, options: list[str]) -> ChoiceResult:
        raise NotImplementedError(
            "JevDecider is untested (no TypeSafe access key) and must not be called in this experiment."
        )
