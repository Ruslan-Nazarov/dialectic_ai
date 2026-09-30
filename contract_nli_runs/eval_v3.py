"""Engine v3 on ContractNLI: an agent acting in the NDA world vs the same model without it.

    python contract_nli_runs/eval_v3.py --world <world.json> [--agent openai:gpt-5-mini] [--repeats 2]

Pairs: the 49 gold-Contradiction pairs the plain model got wrong in plain_scan.json, 20 gold-Contradiction pairs
it got right, 30 Entailment and 30 NotMentioned pairs (random, seed 7) -- so that answering "Contradiction"
everywhere cannot win. Both arms get the same task text; the world arm adds the world to the system prompt and
the world_fit mark. Revisions are off during the measurement (the world must not change mid-run); how often the
agent marked "does not fit" is counted.
"""
import argparse
import asyncio
import json
import random
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from dialectic_world import WorldAdapter  # noqa: E402
from dialectic_world.llm import build_llm  # noqa: E402
from experiments.legacy_world import load_world, LegacyWorldAdapter  # noqa: E402
from types import SimpleNamespace

TASK = """Here is a non-disclosure agreement:
<<<
{text}
>>>
Statement: "{hypothesis}"
Does the agreement entail this statement, contradict it, or not mention it? Answer with exactly one of
Entailment / Contradiction / NotMentioned and quote the clause(s) of the agreement that decide it."""
PLAIN_FORMAT = 'Return only JSON: {"answer": "<Entailment|Contradiction|NotMentioned> -- quoted clauses"}'
WORLD_FORMAT = ('Return only JSON: {"answer": "<Entailment|Contradiction|NotMentioned> -- quoted clauses", '
                '"world_fit": {"fits": true, "process_ids": [], "note": ""}}')


def verdict(text):
    found = re.findall(r"\b(Entailment|Contradiction|NotMentioned|Not Mentioned)\b", text or "")
    return found[0].replace(" ", "") if found else "?"


def select_pairs(data, seed=7):
    scan = json.loads((HERE / "plain_scan.json").read_text(encoding="utf-8"))
    wrong = {(r["doc"], r["hypothesis"]) for r in scan if r["verdict"] != "Contradiction"}
    right = [(r["doc"], r["hypothesis"]) for r in scan if r["verdict"] == "Contradiction"]
    by_label = {"Entailment": [], "NotMentioned": []}
    for doc in data["documents"]:
        for key, a in doc["annotation_sets"][0]["annotations"].items():
            if a["choice"] in by_label:
                by_label[a["choice"]].append((doc["id"], key))
    rng = random.Random(seed)
    pairs = [(d, k, "hard") for d, k in sorted(wrong)]
    pairs += [(d, k, "contradiction_easy") for d, k in rng.sample(sorted(right), 20)]
    pairs += [(d, k, "entailment") for d, k in rng.sample(sorted(by_label["Entailment"]), 30)]
    pairs += [(d, k, "not_mentioned") for d, k in rng.sample(sorted(by_label["NotMentioned"]), 30)]
    return pairs


async def main(args):
    out = Path(args.out)
    if out.exists():
        raise FileExistsError(f"Refusing to overwrite saved evidence: {out}; choose --out")
    data = json.loads(Path(args.dataset).read_text(encoding="utf-8"))
    docs = {d["id"]: d for d in data["documents"]}
    world = load_world(args.world)
    role = "You review non-disclosure agreements."
    systems = {"world": LegacyWorldAdapter(world, max_chars=args.brief).system_prompt(role)}
    if args.placebo:
        placebo = load_world(args.placebo)
        systems["placebo"] = LegacyWorldAdapter(placebo, max_chars=args.brief).system_prompt(role)
    arms = ["plain"] + list(systems)
    pairs = select_pairs(data)
    if args.limit:
        pairs = [p for g in GROUPS for p in [x for x in pairs if x[2] == g][:args.limit]]
    llms = {a: build_llm(args.agent) for a in arms}
    gate = asyncio.Semaphore(args.concurrency)
    rows = []

    async def one(doc_id, key, group, arm, rep):
        doc = docs[doc_id]
        task = TASK.format(text=doc["text"].strip(), hypothesis=data["labels"][key]["hypothesis"])
        if arm == "plain":
            messages = [{"role": "user", "content": task + "\n" + PLAIN_FORMAT}]
        else:
            messages = [{"role": "system", "content": systems[arm]}, {"role": "user", "content": task + "\n" + WORLD_FORMAT}]
        async with gate:
            started = time.monotonic()
            try:
                text = await llms[arm].generate(messages)
            except Exception as exc:  # noqa: BLE001
                text = f"ERROR {type(exc).__name__}: {exc}"
        fit = WorldAdapter.parse_world_fit(text) if arm != "plain" else None
        try:
            answer = json.loads(re.search(r"\{.*\}", text, re.S).group(0)).get("answer", text)
        except Exception:  # noqa: BLE001
            answer = text
        rows.append({"doc": doc_id, "hypothesis": key, "group": group, "arm": arm, "rep": rep,
                     "gold": doc["annotation_sets"][0]["annotations"][key]["choice"], "verdict": verdict(answer),
                     "fits": None if fit is None else fit.fits, "fit_note": fit.note if fit else "",
                     "fit_ids": fit.process_ids if fit else [], "seconds": round(time.monotonic() - started, 1),
                     "answer": str(answer)[:800]})

    await asyncio.gather(*(one(d, k, g, arm, rep) for d, k, g in pairs for arm in arms for rep in range(args.repeats)))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    report(rows, llms, arms, out.with_suffix(".md"), args, SimpleNamespace(**world))


GROUPS = ["hard", "contradiction_easy", "entailment", "not_mentioned"]


def report(rows, llms, arms, path, args, world):
    lines = ["# ContractNLI: agent in the world vs plain model\n",
             f"agent model {args.agent}; world {world.domain!r} v{world.version} ({world.status}); "
             f"repeats {args.repeats}; pairs {len({(r['doc'], r['hypothesis']) for r in rows})}\n",
             "| group | pairs | " + " | ".join(f"{a} accuracy" for a in arms) + " | "
             + " | ".join(f"{a} stable" for a in arms) + " |",
             "|---|---|" + "---|" * (2 * len(arms))]
    for g in GROUPS + ["ALL"]:
        rs = [r for r in rows if g == "ALL" or r["group"] == g]
        acc, stable = {}, {}
        for a in arms:
            ra = [r for r in rs if r["arm"] == a]
            acc[a] = sum(r["verdict"] == r["gold"] for r in ra) / max(1, len(ra))
            by = {}
            for r in ra:
                by.setdefault((r["doc"], r["hypothesis"]), set()).add(r["verdict"])
            stable[a] = sum(len(v) == 1 for v in by.values()) / max(1, len(by))
        n = len({(r["doc"], r["hypothesis"]) for r in rs})
        lines.append(f"| {g} | {n} | " + " | ".join(f"{acc[a]:.0%}" for a in arms) + " | "
                     + " | ".join(f"{stable[a]:.0%}" for a in arms) + " |")
    lines.append("")
    for a in arms:
        if a == "plain":
            continue
        ra = [r for r in rows if r["arm"] == a]
        lines.append(f"{a} world_fit marks: fits={sum(r['fits'] is True for r in ra)}, "
                     f"does not fit={sum(r['fits'] is False for r in ra)}, missing={sum(r['fits'] is None for r in ra)}")
    lines.append("tokens: " + "; ".join(f"{a} {llms[a].usage.total} in {llms[a].usage.calls} calls" for a in arms))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", default=str(ROOT / "experiments/grounding_vs_calibration/data/contract-nli/test.json"))
    p.add_argument("--world", required=True)
    p.add_argument("--placebo", help="a world of the same shape but empty of meaning: controls for the prompt itself")
    p.add_argument("--agent", default="openai:gpt-5-mini")
    p.add_argument("--repeats", type=int, default=2)
    p.add_argument("--concurrency", type=int, default=8)
    p.add_argument("--out", default=str(ROOT / "scratch" / "eval_v3.json"))
    p.add_argument("--brief", type=int, default=8000, help="max chars of the world given to the agent")
    p.add_argument("--limit", type=int, default=0, help="pairs per group, for a dry run")
    asyncio.run(main(p.parse_args()))
