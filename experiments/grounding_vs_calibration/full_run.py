"""Full run: all 258 world-arm answers, all three variants, in parallel.

Token usage is read from each call's own response (ChoiceResult.prompt_tokens/completion_tokens,
CallResult.prompt_tokens/completion_tokens) -- never from a shared before/after counter -- so
concurrency here cannot reproduce the blocks.py race condition documented in
ENGINE_V3_RESULTS_INDEX.md.
"""
from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from data import ROOT, active_process_ids, load_world, load_world_answers
from decider import ChoiceResult, SurrogateDecider
from llm_call import chat_call
from retrieval import PracticeSignal, keyword_search, quote_found_verbatim
from variants import build_state

SURROGATE_MODEL = "gpt-4o-mini"
BASE_URL = "https://api.openai.com/v1"
API_KEY_ENV = "OPENAI_API_KEY"
AGENT_MODEL = "gpt-5-mini"
MAX_WORKERS = 16

GOLD_DATA_PATH = ROOT / "live_runs" / "contract_nli" / "contract-nli" / "test.json"
OUT_DIR = Path(__file__).resolve().parent


def load_contract_texts() -> dict[int, str]:
    with open(GOLD_DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return {d["id"]: d["text"] for d in data["documents"]}


def load_hypothesis_texts() -> dict[str, str]:
    with open(GOLD_DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return {k: v["hypothesis"] for k, v in data["labels"].items()}


def reverdict_from_quote(quote: str, hypothesis_text: str) -> tuple[str, int, int]:
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
    text = result.text.strip()
    label = "NotMentioned"
    for cand in ("Entailment", "Contradiction", "NotMentioned"):
        if cand.lower() in text.lower():
            label = cand
            break
    return label, result.prompt_tokens, result.completion_tokens


def run_variant2_for_answer(decider, a, process_ids) -> ChoiceResult:
    state = build_state(a)
    return decider.choice_binary_none(state, process_ids)


def run_variant3_for_answer(a, contract_texts, hyp_texts) -> dict:
    text = contract_texts.get(a.doc, "")
    hyp_text = hyp_texts.get(a.hypothesis, "")
    hits = keyword_search(text, hyp_text)
    quote = hits[0] if hits else None
    if quote is None:
        return {"signal": PracticeSignal(False, None, None), "prompt_tokens": 0, "completion_tokens": 0}
    found = quote_found_verbatim(text, quote)
    if not found:
        return {"signal": PracticeSignal(False, None, None), "prompt_tokens": 0, "completion_tokens": 0}
    reverdict, pt, ct = reverdict_from_quote(quote, hyp_text)
    return {
        "signal": PracticeSignal(True, reverdict, reverdict == a.verdict),
        "prompt_tokens": pt,
        "completion_tokens": ct,
    }


def main():
    answers = load_world_answers()
    world = load_world()
    process_ids = active_process_ids(world)
    contract_texts = load_contract_texts()
    hyp_texts = load_hypothesis_texts()
    decider = SurrogateDecider(SURROGATE_MODEL, BASE_URL, API_KEY_ENV)

    started = time.monotonic()

    v2_results: list[ChoiceResult] = [None] * len(answers)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {
            ex.submit(run_variant2_for_answer, decider, a, process_ids): i
            for i, a in enumerate(answers)
        }
        for fut in as_completed(futs):
            i = futs[fut]
            v2_results[i] = fut.result()

    v3_out: list[dict] = [None] * len(answers)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {
            ex.submit(run_variant3_for_answer, a, contract_texts, hyp_texts): i
            for i, a in enumerate(answers)
        }
        for fut in as_completed(futs):
            i = futs[fut]
            v3_out[i] = fut.result()

    elapsed = time.monotonic() - started

    v2_prompt_tok = sum(r.prompt_tokens for r in v2_results)
    v2_completion_tok = sum(r.completion_tokens for r in v2_results)
    v3_prompt_tok = sum(o["prompt_tokens"] for o in v3_out)
    v3_completion_tok = sum(o["completion_tokens"] for o in v3_out)

    raw = []
    for i, a in enumerate(answers):
        r2 = v2_results[i]
        s3: PracticeSignal = v3_out[i]["signal"]
        raw.append(
            {
                "doc": a.doc,
                "hypothesis": a.hypothesis,
                "group": a.group,
                "rep": a.rep,
                "gold": a.gold,
                "verdict": a.verdict,
                "correct": a.correct,
                "fits": a.fits,
                "v2_choice": r2.choice,
                "v2_probabilities": r2.probabilities,
                "v2_confidence": r2.confidence,
                "v3_quote_found": s3.quote_found,
                "v3_reverdict": s3.reverdict,
                "v3_reverdict_matches_original": s3.reverdict_matches_original,
            }
        )

    with open(OUT_DIR / "raw_results.json", "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)

    summary = {
        "n_answers": len(answers),
        "n_pairs": len({(a.doc, a.hypothesis) for a in answers}),
        "elapsed_seconds": elapsed,
        "v2_prompt_tokens": v2_prompt_tok,
        "v2_completion_tokens": v2_completion_tok,
        "v3_prompt_tokens": v3_prompt_tok,
        "v3_completion_tokens": v3_completion_tok,
        "v2_calls": len(answers),
        "v3_calls": sum(1 for o in v3_out if o["prompt_tokens"] > 0),
    }
    with open(OUT_DIR / "run_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
