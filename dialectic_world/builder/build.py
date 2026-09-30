"""Building the world of a domain: find_p0 -> iterations of build_iteration+compare_development until
check_opposition confirms an opposite (or iterations_max runs out) -> form_contradiction -> resolve_leap.
Code, not a prompt, decides whether to call each block at all -- prompt_5/6 are only ever invoked once
there is something real for them to work on (ENGINE_V3_ARCHITECTURE.md principle 5, "economy")."""
from dialectic_world.builder.blocks import (Context, build_iteration, check_opposition, compare_development,
                                            find_p0, form_contradiction, resolve_leap)
from dialectic_world.world.model import Process, World
from dialectic_world.world.store import WorldStore
from dialectic_world.provenance import run_metadata


async def build_world(domain: str, ctx: Context, store: WorldStore | None = None) -> World:
    """Builds and saves the world. A block that fails for good leaves the partial world saved with
    status "failed" (for inspection) and re-raises."""
    holder: dict = {"version": max(store.versions(domain), default=0) + 1 if store else 1}
    ctx.trace.event("run_metadata", domain=domain, version=holder["version"], **run_metadata(ctx))
    try:
        return await _build(domain, ctx, store, holder)
    except Exception as exc:
        world = holder.get("world")
        if world is not None:
            world.status = "failed"
            ctx.trace.event("world", status="failed", error=f"{type(exc).__name__}: {exc}"[:500])
            if store and not store.path(world).exists():
                store.save(world)
        raise


async def _build(domain: str, ctx: Context, store: WorldStore | None, holder: dict) -> World:
    s = ctx.settings
    rejected: list[dict] = []
    world = None
    confirmed = None
    for attempt in range(1, s.p0_attempts + 1):
        world = holder["world"] = World(domain=domain, version=holder["version"], rejected_p0=list(rejected))
        ctx.trace.event("p0_attempt", attempt=attempt)
        p0, explanation, verdict, reason = await find_p0(ctx, world, rejected)
        if verdict == "not_suitable":
            rejected.append({"p0": p0.statement, "reason": reason})
            continue
        world.p0, world.p0_explanation = p0, explanation
        world.add(p0)

        for n in range(1, s.iterations_max + 1):
            previous = world.iterations[-1] if world.iterations else None
            iteration = await build_iteration(ctx, world, n, previous)
            world.iterations.append(iteration)
            comparison = await compare_development(ctx, world)
            world.comparisons.append(comparison)
            if comparison.opposition_candidates:
                check = await check_opposition(ctx, world, comparison.opposition_candidates)
                world.opposition_checks.append(check)
                if check.confirmed_opposites:
                    confirmed = check.confirmed_opposites[0]
                    if len(check.confirmed_opposites) > 1:
                        ctx.trace.event("extra_opposites_ignored",
                                        kept=confirmed["process_ref"],
                                        dropped=[c["process_ref"] for c in check.confirmed_opposites[1:]])
                    break
        if confirmed is not None:
            break
        rejected.append({"p0": p0.statement,
                         "reason": f"за {s.iterations_max} итераций не найдена подтверждённая противоположность"})

    if confirmed is None:
        world.rejected_p0 = rejected   # the world's own snapshot predates this attempt's own rejection, if any
        world.status = "no_p0" if world.p0 is None else "no_opposite"
        ctx.trace.event("world", status=world.status)
        if store:
            store.save(world)
        return world

    opposite = _find_by_ref(world, confirmed["process_ref"])
    world.opposite, world.opposite_explanation = opposite, confirmed

    contradiction = await form_contradiction(ctx, world, opposite, confirmed)
    if contradiction is None:
        world.status = "failed"
        ctx.trace.event("world", status=world.status, reason="form_contradiction did not produce CONTRADICTIONS_FORMED")
        if store:
            store.save(world)
        return world
    world.contradiction = contradiction

    resolution = await resolve_leap(ctx, world, opposite, confirmed)
    world.resolution = resolution
    if resolution is None:
        world.status = "leap_not_found"
    elif resolution.kind == "replacement":
        world.status = "built"
    else:
        world.status = "mediated"
    ctx.trace.event("world", status=world.status, processes=len(world.processes))
    if store:
        store.save(world)
    return world


def _find_by_ref(world: World, ref: str) -> Process:
    """prompt_3/4 name processes 'I<iteration>.P<k>'; map that back to this world's generated id: the
    k-th developing process added in iteration <iteration>."""
    m = ref.split(".")
    if len(m) == 2 and m[0].startswith("I") and m[1].startswith("P"):
        it_n, k = int(m[0][1:]), int(m[1][1:])
        it = next((i for i in world.iterations if i.n == it_n), None)
        if it and 1 <= k <= len(it.developing):
            return world.get(it.developing[k - 1])
    raise KeyError(f"opposition_candidates referenced {ref!r}, which no iteration produced")
