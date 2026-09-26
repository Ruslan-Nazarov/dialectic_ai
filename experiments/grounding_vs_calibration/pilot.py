"""Pilot run: 10 real answers, all three variants. Reports cost, then stops (full run needs go-ahead)."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from data import GOLD_FILE, active_process_ids, load_world, load_world_answers
from decider import build_decider
from llm_call import chat_call
from retrieval import QuoteReverdictSignal, keyword_search, quote_found_verbatim
from variants import build_state, variant1_signal, variant2_error_signal

SURROGATE_MODEL = "gpt-4o-mini"
BASE_URL = "https://api.openai.com/v1"
API_KEY_ENV = "OPENAI_API_KEY"
AGENT_MODEL = "gpt-5-mini"  # for the re-verdict call in variant 3, matching the original agent model

GOLD_DATA_PATH = GOLD_FILE


def load_contract_texts() -> dict[int, str]:
    with open(GOLD_DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return {d["id"]: d["text"] for d in data["documents"]}


def load_hypothesis_texts() -> dict[str, str]:
    with open(GOLD_DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return {k: v["hypothesis"] for k, v in data["labels"].items()}


def reverdict_from_quote_tracked(quote: str, hypothesis_text: str, holder: dict) -> str:
    prompt = (
        f"Contract clause: \"{quote}\"\n\nStatement: \"{hypothesis_text}\"\n\n"
        "Based only on this clause, is the statement Entailment, Contradiction, or NotMentioned? "
        "Answer with exactly one of those three words."
    )
    result = chat_call(
        AGENT_MODEL,
        [{"role": "user", "content": prompt}],
        BASE_URL,
        API_KEY_ENV,
        max_tokens=800,
        max_tokens_param="max_completion_tokens",
    )
    holder["prompt_tokens"] = result.prompt_tokens
    holder["completion_tokens"] = result.completion_tokens
    text = result.text.strip()
    for label in ("Entailment", "Contradiction", "NotMentioned"):
        if label.lower() in text.lower():
            return label
    return "NotMentioned"


def main():
    answers = load_world_answers()[:10]
    world = load_world()
    process_ids = active_process_ids(world)
    print(f"active_process_ids={len(process_ids)} (of {len(world['processes'])} total)")
    contract_texts = load_contract_texts()
    hyp_texts = load_hypothesis_texts()

    decider = build_decider(SURROGATE_MODEL, BASE_URL, API_KEY_ENV)

    total_prompt_tok = 0
    total_completion_tok = 0
    total_calls = 0
    started = time.monotonic()

    # Variant 1: no calls.
    v1 = variant1_signal(answers)

    # Variant 2: one Choice call per answer.
    v2_results = []
    for a in answers:
        state = build_state(a)
        r = decider.choice_binary_none(state, process_ids)
        v2_results.append(r)
        total_calls += 1
        total_prompt_tok += r.prompt_tokens
        total_completion_tok += r.completion_tokens
    # Variant 3: one search (no call, code only) + one re-verdict call per answer, when a quote exists.
    v3_signals: list[QuoteReverdictSignal] = []
    for a in answers:
        text = contract_texts.get(a.doc, "")
        hyp_text = hyp_texts.get(a.hypothesis, "")
        hits = keyword_search(text, hyp_text)
        quote = hits[0] if hits else None
        if quote is None:
            v3_signals.append(QuoteReverdictSignal(quote_found=False, reverdict=None, reverdict_matches_original=None))
            continue
        found = quote_found_verbatim(text, quote)
        reverdict = None
        if found:
            call_result_holder = {}
            reverdict = reverdict_from_quote_tracked(quote, hyp_text, call_result_holder)
            total_calls += 1
            total_prompt_tok += call_result_holder.get("prompt_tokens", 0)
            total_completion_tok += call_result_holder.get("completion_tokens", 0)
        v3_signals.append(
            QuoteReverdictSignal(
                quote_found=found,
                reverdict=reverdict,
                reverdict_matches_original=(reverdict == a.verdict) if reverdict else None,
            )
        )

    elapsed = time.monotonic() - started

    # Correctness is ONLY the ContractNLI gold comparison already computed in data.load_world_answers
    # (Answer.correct = verdict == gold). Variant 3's re-verdict is a signal to evaluate, never the
    # ground truth -- it must not be used to define "correct" anywhere in this report.
    correct = [a.correct for a in answers]
    v2_error = variant2_error_signal(v2_results, p_none_threshold=0.5)
    v3_error = [s.error_signal for s in v3_signals]

    n_wrong = sum(not c for c in correct)
    print(f"n_answers_piloted={len(answers)}, wrong per ContractNLI gold={n_wrong}")
    for i, a in enumerate(answers):
        print(
            f"  #{i} doc={a.doc} hyp={a.hypothesis} gold={a.gold} verdict={a.verdict} "
            f"correct={a.correct} | v1_err={v1[i]} v2_err={v2_error[i]} v3_err={v3_error[i]} "
            f"(v3 quote_not_found={v3_signals[i].quote_not_found_signal} "
            f"verdict_disagree={v3_signals[i].verdict_disagreement_signal})"
        )

    def caught(signal):
        return sum(1 for s, c in zip(signal, correct) if s and not c)

    print(f"of {n_wrong} wrong answers -- caught by v1={caught(v1)} v2={caught(v2_error)} v3={caught(v3_error)}")
    print(f"total_calls_made={total_calls} (variant2 + variant3 reverdicts)")
    print(f"total_prompt_tokens={total_prompt_tok} total_completion_tokens={total_completion_tok}")
    print(f"elapsed_seconds={elapsed:.1f}")
    print()
    scale = 258 / len(answers)
    print(f"Cost extrapolation to 258 answers (x{scale:.1f}):")
    print(f"  est. calls ~= {total_calls * scale:.0f}")
    print(f"  est. prompt tokens ~= {total_prompt_tok * scale:.0f}")
    print(f"  est. completion tokens ~= {total_completion_tok * scale:.0f}")
    print(f"  est. wall-clock (serial) ~= {elapsed * scale:.0f}s")


if __name__ == "__main__":
    main()
