"""Step 4 of PREREGISTRATION.md: build world 1 ("fraction arithmetic") only, then stop.

Not a library module reused elsewhere -- a one-shot script, run once, per the preregistration's
"построить мир 1 (дроби) -- стоп, отчёт" step. World 2 (Ratios and proportional reasoning) is a
separate script, run only after the user confirms this report.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from dialectic_world import Context, Settings, WorldAdapter, WorldStore, build_world  # noqa: E402
from dialectic_world.llm import build_llm  # noqa: E402
from dialectic_world.trace import Trace  # noqa: E402

DOMAIN = (
    "How a school student's understanding of fraction arithmetic develops, from the first way of "
    "doing it to a mature understanding. Skills in this topic: equivalent fractions, comparing "
    "fractions, adding and subtracting fractions, multiplying fractions, dividing fractions, mixed "
    "numbers and improper fractions."
)

DATA_DIR = HERE / "data"
WORLDS_DIR = DATA_DIR / "worlds"
TRACE_PATH = DATA_DIR / "traces" / "build_world1.jsonl"


async def main() -> None:
    store = WorldStore(WORLDS_DIR)
    settings = Settings(output_language="en")  # every other field left at its default, per PREREGISTRATION.md step 3
    llm = build_llm(settings.builder_model)
    trace = Trace(TRACE_PATH)
    world = await build_world(DOMAIN, Context(llm=llm, settings=settings, trace=trace), store)

    print("=" * 70)
    print("WORLD 1 -- fraction arithmetic")
    print("=" * 70)
    print(f"status={world.status}, version={world.version}, processes={len(world.processes)}")
    print(f"builder calls={llm.usage.calls}, prompt_tokens={llm.usage.prompt_tokens}, "
          f"completion_tokens={llm.usage.completion_tokens}, total_tokens={llm.usage.total}")
    print(f"saved to: {store.path(world)}")

    p0 = world.p0
    opp = world.opposite
    contr = world.get(world.contradiction.process_id)
    res = world.get(world.resolution.process_id)
    first_iter = world.iterations[0] if world.iterations else None
    developing = [world.get(pid) for pid in (first_iter.developing if first_iter else [])]

    print("\n--- simplest process (P0) ---")
    print(p0.statement)
    print("\n--- first developing processes ---")
    for d in developing[:5]:
        print(f"- {d.statement}")
    print("\n--- opposite ---")
    print(opp.statement)
    print("\n--- contradiction ---")
    print(contr.statement)
    print("\n--- resolution ---")
    print(f"kind={world.resolution.kind}")
    print(res.statement)

    brief = WorldAdapter(world, max_chars=settings.brief_max_chars).brief()
    print(f"\nbrief() length: {len(brief)} chars (max_chars={settings.brief_max_chars})")

    summary = {
        "status": world.status,
        "version": world.version,
        "processes": len(world.processes),
        "builder_calls": llm.usage.calls,
        "prompt_tokens": llm.usage.prompt_tokens,
        "completion_tokens": llm.usage.completion_tokens,
        "total_tokens": llm.usage.total,
        "brief_chars": len(brief),
        "world_path": str(store.path(world)),
    }
    (DATA_DIR / "world1_build_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    asyncio.run(main())
