"""Smoke test, not a preregistered experiment: builds ONE world on the rewritten engine (prompt_1..6,
builder/blocks.py + builder/build.py, current on-disk state) with prompt_language="en", for the
narrowest possible domain -- the bare arithmetic fact "2 + 2", not a topic with development like
"fraction arithmetic" and not even a described situation like build_instance1.py's "car turns at an
intersection". Answers the open question from that script's docstring, one step further down: does
FindP0 even accept something this bare as a subject, and if so does the flattened P0-only-iterates
architecture (see dialectic_world/world/model.py's module docstring) produce a sensible
opposite/contradiction/resolution -- or hit p0_attempts / no_opposite / failed. Stops after one world;
nothing here decides a dataset, a metric, or whether to attach Jev to this pattern.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from dialectic_world import Context, Settings, WorldAdapter, WorldStore, build_world  # noqa: E402
from dialectic_world.llm import build_llm  # noqa: E402
from dialectic_world.trace import Trace  # noqa: E402

DOMAIN = "2 + 2"

DATA_DIR = HERE / "data"
WORLDS_DIR = DATA_DIR / "worlds"
TRACE_PATH = DATA_DIR / "traces" / "build_addition_en.jsonl"


async def main() -> None:
    store = WorldStore(WORLDS_DIR)
    settings = Settings(prompt_language="en")  # every other field left at its default
    llm = build_llm(settings.builder_model)
    trace = Trace(TRACE_PATH)
    world = await build_world(DOMAIN, Context(llm=llm, settings=settings, trace=trace), store)

    print("=" * 70)
    print(f"ADDITION WORLD (new engine, prompt_language=en) -- {DOMAIN!r}")
    print("=" * 70)
    print(f"status={world.status}, version={world.version}, processes={len(world.processes)}")
    print(f"builder calls={llm.usage.calls}, prompt_tokens={llm.usage.prompt_tokens}, "
          f"completion_tokens={llm.usage.completion_tokens}, total_tokens={llm.usage.total}")
    print(f"saved to: {store.path(world)}")
    print(f"rejected P0 candidates: {len(world.rejected_p0)}")
    for r in world.rejected_p0:
        print(f"  - {r['p0']!r}: {r['reason']}")

    if world.p0:
        print("\n--- simplest process (P0) ---")
        print(world.p0.line())
        print(json.dumps(world.p0_explanation, ensure_ascii=False, indent=2))

    for it in world.iterations:
        print(f"\n--- iteration {it.n} developing processes ---")
        for pid in it.developing:
            print(f"- {world.get(pid).line()}")

    if world.status == "no_opposite":
        print(f"\n(no confirmed opposite found within {settings.iterations_max} iteration(s) / "
              f"{settings.p0_attempts} P0 attempt(s) -- stopping here, see trace for the model's own reasoning)")
        return

    if world.opposite:
        print("\n--- opposite ---")
        print(world.opposite.line())
        print(json.dumps(world.opposite_explanation, ensure_ascii=False, indent=2))

    if world.status == "failed":
        print("\n(world failed after finding an opposite -- see trace)")
        return

    if world.contradiction:
        print("\n--- contradiction ---")
        print(world.get(world.contradiction.process_id).line())
        print(f"  unity: {world.contradiction.unity}")

    if world.status == "leap_not_found":
        print("\n(no resolving leap found -- see trace)")
        return

    if world.resolution:
        print("\n--- resolution ---")
        print(f"kind={world.resolution.kind}")
        print(world.get(world.resolution.process_id).line())
        print(f"  explanation: {world.resolution.explanation}")

    brief = WorldAdapter(world, max_chars=settings.brief_max_chars).brief()
    print(f"\nbrief() length: {len(brief)} chars (max_chars={settings.brief_max_chars})")
    print(brief)

    summary = {
        "domain": DOMAIN,
        "prompt_language": settings.prompt_language,
        "status": world.status,
        "version": world.version,
        "processes": len(world.processes),
        "rejected_p0": len(world.rejected_p0),
        "builder_calls": llm.usage.calls,
        "prompt_tokens": llm.usage.prompt_tokens,
        "completion_tokens": llm.usage.completion_tokens,
        "total_tokens": llm.usage.total,
        "brief_chars": len(brief),
        "world_path": str(store.path(world)),
    }
    (DATA_DIR / "addition_en_build_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    asyncio.run(main())
