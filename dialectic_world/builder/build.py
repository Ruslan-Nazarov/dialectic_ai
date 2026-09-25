"""Building the world of a domain, in the order of architecture 4.2."""
from dialectic_world.builder.blocks import Context, contradiction, find_p0, resolve
from dialectic_world.builder.bundle import run_bundle
from dialectic_world.world.model import Contradiction, Opposite, P0Record, Resolution, World
from dialectic_world.world.store import WorldStore


async def develop_from_opposite(ctx: Context, world: World) -> None:
    """Steps 4-7: the opposite's bundle, the contradiction, its bundle, the resolution. Also used by a
    revision that changed the opposite or what it rests on."""
    for name in ("opposite", "contradiction"):
        world.bundles.pop(name, None)
    world.processes = {pid: p for pid, p in world.processes.items()
                       if p.bundle not in ("opposite", "contradiction") and p.role not in ("contradiction", "resolution")}
    await run_bundle(ctx, world, "opposite", world.get(world.opposite.process_id))
    await develop_from_contradiction(ctx, world, new_contradiction=True)


async def develop_from_contradiction(ctx: Context, world: World, new_contradiction: bool) -> None:
    if new_contradiction:
        c, unity = await contradiction(ctx, world)
        world.add(c)
        world.contradiction = Contradiction(process_id=c.id, unity=unity)
        world.bundles.pop("contradiction", None)
        await run_bundle(ctx, world, "contradiction", c)
    r, kind, explanation = await resolve(ctx, world)
    world.add(r)
    world.resolution = Resolution(process_id=r.id, kind=kind, explanation=explanation)


async def build_world(domain: str, ctx: Context, store: WorldStore | None = None) -> World:
    """Builds and saves the world. A block that fails for good leaves the partial world saved with
    status "failed" (for inspection) and re-raises."""
    holder: dict = {}
    try:
        return await _build(domain, ctx, store, holder)
    except Exception as exc:
        world = holder.get("world")
        if world is not None:
            world.status = "failed"
            ctx.trace.event("world", status="failed", error=f"{type(exc).__name__}: {exc}"[:500])
            if store:
                store.save(world)
        raise


async def _build(domain: str, ctx: Context, store: WorldStore | None, holder: dict) -> World:
    s = ctx.settings
    rejected: list[dict] = []
    world = None
    for attempt in range(1, s.p0_attempts + 1):
        world = holder["world"] = World(domain=domain, rejected_p0=list(rejected))
        ctx.carry = ""
        ctx.trace.event("p0_attempt", attempt=attempt)
        p0, from_leap = await find_p0(ctx, world, rejected)
        world.add(p0)
        world.p0 = P0Record(process_id=p0.id, from_leap=from_leap, attempt=attempt)
        found = await run_bundle(ctx, world, "p0", p0)
        if found.opposite_id:
            world.opposite = Opposite(process_id=found.opposite_id, why_not_required=found.why_not_required)
            break
        rejected.append({"p0": p0.statement,
                         "reason": f"за {s.iterations_max} итераций среди развивающих процессов не найден противоположный"})
    else:
        world.status = "no_opposite"
        ctx.trace.event("world", status=world.status)
        if store:
            store.save(world)
        return world
    await develop_from_opposite(ctx, world)
    world.status = "built"
    ctx.trace.event("world", status=world.status, processes=len(world.processes))
    if store:
        store.save(world)
    return world
