"""Current-schema revision demo with an explicitly supplied external observation.

For the historical 25 September demo, see research_artifacts/legacy_v3.
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
from dialectic_world import Context, Settings, WorldFit, WorldStore
from dialectic_world.world.model import World
from dialectic_world.adapter.revise import revise_world
from dialectic_world.llm import build_llm
from dialectic_world.trace import Trace


async def run(args):
    raw = json.loads(args.world.read_text(encoding="utf-8"))
    if "bundles" in raw:
        raise ValueError("Legacy bundle-worlds cannot be revised by the current engine; see docs/REPRODUCIBILITY.md")
    world = World.model_validate(raw)
    if any(pid not in world.processes or world.get(pid).status != "active" for pid in args.process_id):
        raise ValueError("Every --process-id must be active in the supplied world")
    ctx = Context(llm=build_llm(args.model), settings=Settings(builder_model=args.model),
                  trace=Trace(args.out / "revision.jsonl"))
    new = await revise_world(ctx, world, WorldFit(fits=False, process_ids=args.process_id, note=args.note),
                             args.data, WorldStore(args.out))
    print(json.dumps({"version": new.version, "parent_version": new.parent_version,
                      "status": new.status, "revision": new.revisions[-1].model_dump()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    load_dotenv(ROOT / ".env")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--world", type=Path, required=True)
    p.add_argument("--process-id", action="append", required=True)
    p.add_argument("--note", required=True)
    p.add_argument("--data", required=True)
    p.add_argument("--model", default="openai:gpt-5")
    p.add_argument("--out", type=Path, default=ROOT / "scratch" / "revision_demo")
    asyncio.run(run(p.parse_args()))
