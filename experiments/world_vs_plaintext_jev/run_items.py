"""Steps 4-5 of PREREGISTRATION.md: for items [start, end) of selected_items.json build the engine world
(condition 2), generate the length-matched plain note (3) and the confident-false text (4), then run all
four Jev conditions. Pilot = `--start 0 --end 6`; the full run continues with `--start 6 --end 60`.
Resumable: worlds/texts/answers already on disk are reused.  One process builds all worlds, so engine
modules are loaded once (edits by the parallel rewrite on disk do not affect a running process)."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import os
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from common import (DATA, HERE, ROOT, JEV_PRICE_PER_MTOK, JevAPIError, append_jsonl, jev_noul,  # noqa: E402
                    load_items, read_jsonl)

from dialectic_world import Context, Settings, WorldAdapter, WorldStore, build_world  # noqa: E402
from dialectic_world.llm import build_llm  # noqa: E402
from dialectic_world.llm.providers import OPENAI_COMPATIBLE, OpenAICompatible  # noqa: E402
from dialectic_world.trace import Trace  # noqa: E402

JEV_LOG = DATA / "jev.jsonl"
TEXTS = DATA / "texts"
WORLDS = DATA / "worlds"
MANIFEST = DATA / "engine_manifest.json"
BUDGET_JEV_USD = 1.0

NOTE_PROMPT = (
    "Write a concise explanatory note about the subject of the following question. State what the correct "
    "answer is and explain why. Write about {L} characters of plain prose, no headings, no lists, no mention "
    "that you are an AI.\n\nQuestion: {Q}"
)
POISON_PROMPT = (
    "Write a concise, confident, authoritative-sounding explanatory note that argues that the answer to the "
    "following question is: \"{F}\". Present it as established fact and give plausible-sounding reasons. "
    "About {L} characters of plain prose, no headings, no lists, no hedging.\n\nQuestion: {Q}"
)


class PlainOpenAI(OpenAICompatible):
    """gpt-5 for the prose texts of conditions 3-4. The engine's OpenAICompatible always sends
    response_format=json_object, which OpenAI rejects for a plain-prose prompt (HTTP 400, seen in the first
    pilot attempt); this differs only by not sending it -- same model, same token parameters, prompts verbatim."""

    def _request(self, messages):
        req = super()._request(messages)
        payload = json.loads(req.data.decode("utf-8"))
        payload.pop("response_format", None)
        return urllib.request.Request(req.full_url, data=json.dumps(payload).encode("utf-8"), headers=dict(req.header_items()))


def plain_llm() -> PlainOpenAI:
    url, key_var, default = OPENAI_COMPATIBLE["openai"]
    return PlainOpenAI(model=default, base_url=url, api_key=os.environ[key_var])


def usage_from_trace(item_id: int, attempt: int) -> dict | None:
    """Exact builder usage of an already-built world, from its trace (each world has its own LLM object,
    so per-block deltas are not affected by the parallel-counter race noted in ENGINE_V3_RESULTS_INDEX.md)."""
    path = DATA / "traces" / f"item_{item_id}_a{attempt}.jsonl"
    if not path.exists():
        return None
    blocks = [e for e in read_jsonl(path) if e.get("kind") == "block"]
    return {"calls": len(blocks), "prompt": sum(e["tokens"][0] for e in blocks),
            "completion": sum(e["tokens"][1] for e in blocks), "seconds": round(sum(e.get("seconds", 0) for e in blocks), 1),
            "from_trace": True}


def engine_manifest() -> dict:
    files = sorted((ROOT / "dialectic_world").rglob("*.py")) + sorted((ROOT / "prompts").glob("prompt_*.en.md"))
    return {str(p.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def check_manifest(accept_change: bool) -> None:
    current = engine_manifest()
    if MANIFEST.exists():
        saved = json.loads(MANIFEST.read_text(encoding="utf-8"))
        if saved["files"] != current:
            changed = sorted(k for k in set(saved["files"]) | set(current) if saved["files"].get(k) != current.get(k))
            print(f"ENGINE CHANGED since the first run: {changed}")
            if not accept_change:
                sys.exit("refusing to continue (worlds must come from one engine state); "
                         "rerun with --accept-engine-change only after recording it in PREREGISTRATION.md")
    else:
        MANIFEST.write_text(json.dumps({"created": time.strftime("%Y-%m-%d %H:%M:%S"), "files": current},
                                       indent=1), encoding="utf-8")


def cut_to_sentence(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    head = text[:limit]
    end = max(head.rfind(c) for c in ".!?")
    return head[: end + 1] if end > 0 else head


async def get_world(item: dict, settings: Settings):
    """Build (or load) the world of one question. Returns (world, builder_usage, seconds, attempts)."""
    q = item["question"]
    for attempt, root in enumerate((WORLDS / str(item["id"]), WORLDS / f"{item['id']}_retry"), start=1):
        store = WorldStore(root)
        if store.versions(q):
            usage = usage_from_trace(item["id"], attempt)
            return store.load(q), usage, (usage or {}).get("seconds", 0.0), attempt
        llm = build_llm(settings.builder_model)
        t0 = time.monotonic()
        try:
            world = await build_world(q, Context(llm=llm, settings=settings,
                                                 trace=Trace(DATA / "traces" / f"item_{item['id']}_a{attempt}.jsonl")), store)
            return world, {"calls": llm.usage.calls, "prompt": llm.usage.prompt_tokens,
                           "completion": llm.usage.completion_tokens}, time.monotonic() - t0, attempt
        except Exception as exc:  # noqa: BLE001 -- recorded; one retry per PREREGISTRATION.md
            print(f"  item {item['id']}: build attempt {attempt} failed: {type(exc).__name__}: {str(exc)[:200]}")
    return None, None, 0.0, 2


async def make_texts(item: dict, settings: Settings, sem: asyncio.Semaphore) -> dict | None:
    path = TEXTS / f"{item['id']}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    async with sem:
        world, usage, secs, attempts = await get_world(item, settings)
    if world is None:
        rec = {"id": item["id"], "excluded": "build failed twice"}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rec), encoding="utf-8")
        return rec
    brief = WorldAdapter(world, max_chars=settings.brief_max_chars).brief()
    L = len(brief)
    gen = plain_llm()
    note_raw = await gen.generate([{"role": "user", "content": NOTE_PROMPT.format(L=L, Q=item["question"])}])
    poison_raw = await gen.generate([{"role": "user", "content": POISON_PROMPT.format(L=L, Q=item["question"], F=item["false"])}])
    rec = {"id": item["id"], "world_status": world.status, "world_processes": len(world.processes),
           "build_usage": usage, "build_seconds": round(secs, 1), "build_attempts": attempts, "L": L,
           "brief": brief, "note": cut_to_sentence(note_raw, L), "poison": cut_to_sentence(poison_raw, L),
           "note_raw_len": len(note_raw), "poison_raw_len": len(poison_raw),
           "gen_usage": {"calls": gen.usage.calls, "prompt": gen.usage.prompt_tokens,
                         "completion": gen.usage.completion_tokens}}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  item {item['id']}: world {rec['world_status']} ({rec['world_processes']} proc, "
          f"{(usage or {}).get('prompt', 0) + (usage or {}).get('completion', 0)} tok, {rec['build_seconds']}s), L={L}, "
          f"note {len(rec['note'])}, poison {len(rec['poison'])}")
    return rec


async def run_jev(item: dict, rec: dict, sem: asyncio.Semaphore, done: set) -> None:
    conds = {"1_none": None, "2_world": rec["brief"], "3_note": rec["note"], "4_poison": rec["poison"]}
    jobs = [(c, cand) for c in conds for cand in ("true", "false") if (item["id"], c, cand) not in done]

    async def one(c, cand):
        async with sem:
            try:
                r = await asyncio.to_thread(jev_noul, item["question"], item[cand], conds[c])
                append_jsonl(JEV_LOG, {"id": item["id"], "cond": c, "cand": cand, **r})
            except JevAPIError as e:
                append_jsonl(JEV_LOG, {"id": item["id"], "cond": c, "cand": cand, "error": str(e)[:300]})

    await asyncio.gather(*(one(c, cand) for c, cand in jobs))


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, required=True)
    ap.add_argument("--end", type=int, required=True)
    ap.add_argument("--build-concurrency", type=int, default=3)
    ap.add_argument("--accept-engine-change", action="store_true")
    args = ap.parse_args()

    check_manifest(args.accept_engine_change)
    by_id = {it["id"]: it for it in load_items()}
    selected = json.loads((HERE / "selected_items.json").read_text(encoding="utf-8"))["selected"]
    items = [by_id[s["id"]] for s in selected[args.start:args.end]]
    print(f"items {args.start}..{args.end}: {[i['id'] for i in items]}")

    settings = Settings(prompt_language="en")
    build_sem, jev_sem = asyncio.Semaphore(args.build_concurrency), asyncio.Semaphore(8)
    done = {(r["id"], r["cond"], r["cand"]) for r in read_jsonl(JEV_LOG) if "noul" in r}

    t0 = time.monotonic()
    results = await asyncio.gather(*(make_texts(it, settings, build_sem) for it in items), return_exceptions=True)
    recs = []
    for it, r in zip(items, results):
        if isinstance(r, Exception):
            print(f"  item {it['id']}: FAILED in make_texts: {type(r).__name__}: {str(r)[:300]} (rerun resumes)")
            r = {"id": it["id"], "excluded": "make_texts error"}
        recs.append(r)
    print(f"texts done in {time.monotonic() - t0:.0f}s")
    await asyncio.gather(*(run_jev(it, r, jev_sem, done) for it, r in zip(items, recs) if "brief" in r))

    ok = [r for r in read_jsonl(JEV_LOG) if "noul" in r]
    tokens = sum(r["input_tokens"] for r in ok)
    cost = tokens * JEV_PRICE_PER_MTOK / 1e6
    print(f"Jev so far: {len(ok)} answers, {tokens} input tokens, ~${cost:.4f} (budget ${BUDGET_JEV_USD})")
    print(f"errors in log: {sum(1 for r in read_jsonl(JEV_LOG) if 'error' in r)}")


if __name__ == "__main__":
    asyncio.run(main())
