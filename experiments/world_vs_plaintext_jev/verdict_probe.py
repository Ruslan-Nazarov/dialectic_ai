"""Probe, not a preregistered run: the "world verdict" pipeline on the 6 pilot items (worlds and notes already
built by run_items.py -- no new world builds).

  1. For each item and each candidate answer (true / false) a gpt-5 call reads ONE reference text (the world
     brief, or the length-matched plain note) and returns a verdict on the candidate: fits / contradicts /
     not_addressed (+ one-sentence reason).
  2. Jev then gets the question and ONLY that verdict (key `consistency_check`), not the reference text, and
     answers the usual noul "is the candidate a correct answer?".
Conditions: 1_none (existing pilot answers) vs 5_world_verdict vs 6_note_verdict. Also reported: how often the
verdict itself is right (fits for the true answer, contradicts for the false one) -- world vs note.
"""
from __future__ import annotations

import asyncio
import json
import statistics
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from common import DATA, JEV_PRICE_PER_MTOK, append_jsonl, jev_noul, load_items, read_jsonl  # noqa: E402

from dialectic_world.builder.blocks import extract_json  # noqa: E402
from dialectic_world.llm import build_llm  # noqa: E402

PILOT_IDS = [595, 99, 28, 702, 236, 202]
VERDICTS = DATA / "verdicts.jsonl"
JEV_V = DATA / "jev_verdict.jsonl"
ALLOWED = {"fits", "contradicts", "not_addressed"}

PROMPT = (
    "You are given a reference description and a question with one candidate answer. Decide whether the "
    "candidate answer fits the reference description, contradicts it, or is not addressed by it. Use only the "
    "reference description as your standard; do not use outside knowledge to override it. If the description "
    "says nothing that bears on the candidate, answer \"not_addressed\".\n\n"
    "Reference description:\n{ref}\n\nQuestion: {q}\nCandidate answer: {a}\n\n"
    "Return a JSON object: {{\"verdict\": \"fits\" | \"contradicts\" | \"not_addressed\", "
    "\"reason\": \"<one or two sentences>\"}}"
)


async def get_verdict(llm, sem, item, src, ref, cand) -> dict:
    key = {"id": item["id"], "src": src, "cand": cand}
    text = ""
    for _ in range(2):
        async with sem:
            text = await llm.generate([{"role": "user", "content": PROMPT.format(ref=ref, q=item["question"], a=item[cand])}])
        try:
            data = extract_json(text)
            if data.get("verdict") in ALLOWED and str(data.get("reason", "")).strip():
                rec = {**key, "verdict": data["verdict"], "reason": str(data["reason"]).strip()}
                append_jsonl(VERDICTS, rec)
                return rec
        except ValueError:
            pass
    rec = {**key, "verdict": "error", "reason": text[:200]}
    append_jsonl(VERDICTS, rec)
    return rec


def check_text(v: dict) -> str:
    return f"Consistency check of this candidate answer against a reference description: {v['verdict']}. {v['reason']}"


async def main() -> None:
    by_id = {it["id"]: it for it in load_items()}
    texts = {i: json.loads((DATA / "texts" / f"{i}.json").read_text(encoding="utf-8")) for i in PILOT_IDS}
    done = {(r["id"], r["src"], r["cand"]): r for r in read_jsonl(VERDICTS) if r["verdict"] != "error"}

    llm, sem = build_llm("openai:gpt-5"), asyncio.Semaphore(8)
    jobs = [(i, src, cand) for i in PILOT_IDS for src in ("world", "note") for cand in ("true", "false") if (i, src, cand) not in done]
    print(f"verdict calls to make: {len(jobs)} (already done: {len(done)})")
    refs = {"world": "brief", "note": "note"}
    out = await asyncio.gather(*(get_verdict(llm, sem, by_id[i], src, texts[i][refs[src]], cand) for i, src, cand in jobs))
    for r in out:
        done[(r["id"], r["src"], r["cand"])] = r
    print(f"gpt-5 verdict tokens: prompt {llm.usage.prompt_tokens}, completion {llm.usage.completion_tokens}")
    bad = [k for k, v in done.items() if v["verdict"] == "error"]
    if bad:
        sys.exit(f"verdict errors for {bad}; rerun resumes")

    jev_done = {(r["id"], r["cond"], r["cand"]) for r in read_jsonl(JEV_V) if "noul" in r}
    for i in PILOT_IDS:
        for cond, src in (("5_world_verdict", "world"), ("6_note_verdict", "note")):
            for cand in ("true", "false"):
                if (i, cond, cand) in jev_done:
                    continue
                v = done[(i, src, cand)]
                r = await asyncio.to_thread(jev_noul, by_id[i]["question"], by_id[i][cand], check_text(v), "consistency_check")
                append_jsonl(JEV_V, {"id": i, "cond": cond, "cand": cand, **r})

    base = {(r["id"], r["cond"], r["cand"]): r["noul"] for r in read_jsonl(DATA / "jev.jsonl") if "noul" in r}
    new = {(r["id"], r["cond"], r["cand"]): r["noul"] for r in read_jsonl(JEV_V) if "noul" in r}
    noul = {**base, **new}

    print("\nverdicts (want: true answer -> fits, false answer -> contradicts):")
    print("  id   src   | true answer            | false answer")
    for i in PILOT_IDS:
        for src in ("world", "note"):
            t, f = done[(i, src, "true")], done[(i, src, "false")]
            print(f"  {i:<4} {src:<5} | {t['verdict']:<14}         | {f['verdict']}")
    for src in ("world", "note"):
        ok = sum((done[(i, src, 'true')]['verdict'] == 'fits') + (done[(i, src, 'false')]['verdict'] == 'contradicts') for i in PILOT_IDS)
        print(f"  {src}: verdict correct on {ok}/12")

    def margin(i, c):
        return noul[(i, c, "true")] - noul[(i, c, "false")]

    print("\nJev margin = noul(true) - noul(false):")
    print("  id    none   world_verdict  note_verdict   |  (context as text, from pilot: world / note)")
    for i in PILOT_IDS:
        print(f"  {i:<5} {margin(i, '1_none'):+.2f}   {margin(i, '5_world_verdict'):+.2f}          "
              f"{margin(i, '6_note_verdict'):+.2f}          |  {margin(i, '2_world'):+.2f} / {margin(i, '3_note'):+.2f}")
    for c in ("1_none", "5_world_verdict", "6_note_verdict", "2_world", "3_note"):
        ms = [margin(i, c) for i in PILOT_IDS]
        acc = statistics.mean(1.0 if x > 0 else 0.5 if x == 0 else 0.0 for x in ms)
        print(f"  {c:<16} mean margin {statistics.mean(ms):+.3f}  pair-acc {acc:.3f}")
    toks = sum(r["input_tokens"] for r in read_jsonl(JEV_V) if "noul" in r)
    print(f"\nJev tokens this probe: {toks} (~${toks * JEV_PRICE_PER_MTOK / 1e6:.5f})")

    print("\nsample reasons (item 99, world):")
    for cand in ("true", "false"):
        print(f"  [{cand}] {done[(99, 'world', cand)]['verdict']}: {done[(99, 'world', cand)]['reason']}")


if __name__ == "__main__":
    asyncio.run(main())
