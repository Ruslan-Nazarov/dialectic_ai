"""A live local revision of the NDA world, with the world_fit mark given by hand (no agent produced one)."""
import asyncio, glob, json, sys, time
from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT)); load_dotenv(ROOT / ".env")
from dialectic_world import Context, Settings, WorldFit, WorldStore
from dialectic_world.adapter.revise import revise_world
from dialectic_world.llm import build_llm
from dialectic_world.trace import Trace

async def main():
    store = WorldStore(ROOT / "live_runs" / "v3_worlds")
    path = glob.glob(str(ROOT / "live_runs" / "v3_worlds" / "*" / "v1.json"))[0]
    from dialectic_world.world.model import World
    world = World.model_validate_json(Path(path).read_text(encoding="utf-8"))
    llm = build_llm("openai:gpt-5")
    ctx = Context(llm=llm, settings=Settings(), trace=Trace(ROOT / "live_runs" / "v3_worlds" / "revise.jsonl"))
    fit = WorldFit(fits=False, process_ids=["Ped0e6b"], note=(
        "В реальных договорах и их разметке разрешение, данное только с предварительного письменного согласия "
        "раскрывающей стороны (копировать, передавать третьим лицам), считается запретом с исключением, а не "
        "правом получателя: утверждение 'получатель может копировать' такому договору противоречит. В картине мира "
        "режим допустимого обращения не различает право получателя и разрешение по согласию."))
    data = ("Договор 85 (ContractNLI): 'the Receiving Party is not entitled to copy the Information' без подписанного "
            "заявления; разметка: утверждение 'Receiving Party may create a copy of some Confidential Information' — "
            "Contradiction.")
    started = time.monotonic()
    new = await revise_world(ctx, world, fit, data, store)
    changed = [pid for pid in new.processes if pid not in world.processes]
    print(json.dumps({"version": new.version, "status": new.status, "summary": new.revisions[-1].summary,
                      "affected": new.revisions[-1].affected, "new_processes": len(changed),
                      "p0_bundle_iterations": [len(world.bundles['p0'].iterations), len(new.bundles['p0'].iterations)],
                      "opposite_same": new.opposite == world.opposite, "calls": llm.usage.calls,
                      "tokens": llm.usage.total, "seconds": round(time.monotonic() - started)}, ensure_ascii=False, indent=1))
    for pid in new.last_iteration("p0").developing:
        print(("NEW " if pid in changed else "    ") + new.get(pid).line()[:260])

asyncio.run(main())
