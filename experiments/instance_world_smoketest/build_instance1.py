"""Smoke test, not a preregistered experiment: builds ONE world whose domain is a single concrete
instance ("машина поворачивает на перекрёстке"), not a topic -- to see whether the existing pipeline
(dialectic_world/builder), unmodified, produces a sensible P0/opposite/contradiction/resolution when
fed an already-happening process instead of a "how understanding of X develops" domain description.
Stops after one world; nothing here decides a dataset or a metric.
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

DOMAIN = "Машина поворачивает на перекрёстке."

DATA_DIR = HERE / "data"
WORLDS_DIR = DATA_DIR / "worlds"
TRACE_PATH = DATA_DIR / "traces" / "build_instance1.jsonl"


async def main() -> None:
    store = WorldStore(WORLDS_DIR)
    settings = Settings()  # every field left at its default -- this is what the smoke test is checking
    llm = build_llm(settings.builder_model)
    trace = Trace(TRACE_PATH)
    world = await build_world(DOMAIN, Context(llm=llm, settings=settings, trace=trace), store)

    print("=" * 70)
    print(f"INSTANCE WORLD -- {DOMAIN!r}")
    print("=" * 70)
    print(f"status={world.status}, version={world.version}, processes={len(world.processes)}")
    print(f"builder calls={llm.usage.calls}, prompt_tokens={llm.usage.prompt_tokens}, "
          f"completion_tokens={llm.usage.completion_tokens}, total_tokens={llm.usage.total}")
    print(f"saved to: {store.path(world)}")

    if world.status != "built":
        print(f"\n(world not fully built: status={world.status!r} -- see trace for details)")
        return

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
    print(f"  why P0 not required: {world.opposite.why_not_required}")
    print("\n--- contradiction ---")
    print(contr.statement)
    print(f"  unity: {world.contradiction.unity}")
    print("\n--- resolution ---")
    print(f"kind={world.resolution.kind}")
    print(res.statement)
    print(f"  explanation: {world.resolution.explanation}")

    brief = WorldAdapter(world, max_chars=settings.brief_max_chars).brief()
    print(f"\nbrief() length: {len(brief)} chars (max_chars={settings.brief_max_chars})")

    summary = {
        "domain": DOMAIN,
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
    (DATA_DIR / "instance1_build_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    asyncio.run(main())
