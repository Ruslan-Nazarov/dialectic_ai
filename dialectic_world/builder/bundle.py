"""A bundle with iterations (architecture 4.1). The code drives it; the blocks do the steps.

Iteration 1: developing processes one at a time, each from the root and the ones already got (A 4.2) --
sequentially, never in parallel; then the internal processes of each, in parallel (they are independent,
A 4.5); then one comparison (A 4.7). The next iteration carries out the variant of A 4.6 that the
comparison chose. The p0 bundle stops when the comparison finds the opposite (A 4.8); the opposite's and
the contradiction's bundles stop when the comparison says their development is sufficient; every bundle
stops at `iterations_max`."""
import asyncio

from dialectic_world.builder.blocks import Context, compare, internals, next_developing
from dialectic_world.world.model import Bundle, Comparison, Iteration, Process, World, new_id


async def _develop(ctx: Context, world: World, bundle: str, root: Process, n: int, at_least: int, at_most: int,
                   changes: str = "", agent_data: str = "") -> list[str]:
    new: list[str] = []
    while len(new) < at_most:
        process, more = await next_developing(ctx, world, bundle, root, n, len(new), changes, agent_data)
        world.add(process)
        new.append(process.id)
        if not more and len(new) >= at_least:
            break
    return new


async def _internals(ctx: Context, world: World, bundle: str, n: int, dev_ids: list[str],
                     previous: dict[str, list[str]], agent_data: str = "") -> dict[str, list[str]]:
    carry = ctx.carry
    results = await asyncio.gather(*(
        internals(ctx, world, bundle, world.get(pid), n, [world.get(i) for i in previous.get(pid, [])], agent_data, carry)
        for pid in dev_ids))
    out = {}
    for pid, items in zip(dev_ids, results):
        for p in items:
            world.add(p)
        out[pid] = [p.id for p in items]
    return out


async def next_iteration(ctx: Context, world: World, bundle: str, root: Process, plan: Comparison,
                         agent_data: str = "") -> Iteration:
    """Carries out the A 4.6 variant chosen in `plan` (the previous comparison) as a new iteration."""
    s = ctx.settings
    prev = world.last_iteration(bundle)
    n = prev.n + 1
    variant = plan.next_variant or 1
    for pid in plan.retire:
        world.get(pid).status = "retired"
    kept = [pid for pid in prev.developing if pid not in plan.retire]
    promoted = []
    for iid in plan.promote:          # an internal process becomes a developing one (owner, 2026-09-25)
        internal = world.get(iid)
        p = world.add(Process(id=new_id("P"), source=internal.source, target=internal.target,
                              statement=internal.statement, role="developing", bundle=bundle, iteration=n,
                              derived_from=[iid, internal.parent_id]))
        promoted.append(p.id)
    developing = kept + promoted
    added: list[str] = []
    if variant in (2, 3):
        room = s.developing_max - len(developing)
        need = max(0, s.developing_min - len(developing))
        if room > 0:
            added = await _develop(ctx, world, bundle, root, n, need, room, plan.next_changes, agent_data)
        developing += added
    if variant == 1:
        redo = kept                                  # same developing processes, new internal ones
    elif variant == 2:
        redo = []                                    # internal processes unchanged
    else:
        redo = [pid for pid in (plan.redo_internals or kept) if pid in kept]
    fresh = promoted + added
    internal = {pid: prev.internal.get(pid, []) for pid in kept if pid not in redo}
    internal.update(await _internals(ctx, world, bundle, n, redo + fresh,
                                     {pid: prev.internal.get(pid, []) for pid in redo}, agent_data))
    it = Iteration(n=n, variant=variant, developing=developing, internal=internal)
    world.bundles[bundle].iterations.append(it)
    return it


async def run_bundle(ctx: Context, world: World, bundle: str, root: Process, agent_data: str = "",
                     iterations: int | None = None) -> Comparison:
    """Runs (or, when the bundle already has iterations, continues) a bundle; returns its last comparison."""
    s = ctx.settings
    limit = iterations or s.iterations_max
    b = world.bundles.setdefault(bundle, Bundle(root_id=root.id))
    done = 0
    if not b.iterations:
        dev = await _develop(ctx, world, bundle, root, 1, s.developing_min, s.developing_max, agent_data=agent_data)
        b.iterations.append(Iteration(n=1, developing=dev))
        b.iterations[-1].internal = await _internals(ctx, world, bundle, 1, dev, {}, agent_data)
    else:
        await next_iteration(ctx, world, bundle, root, b.iterations[-1].comparison or Comparison(next_variant=1),
                             agent_data)
    while True:
        done += 1
        it = b.iterations[-1]
        last = done >= limit
        it.comparison = await compare(ctx, world, bundle, root, it.n, last, agent_data)
        c = it.comparison
        if (bundle == "p0" and c.opposite_id) or (bundle != "p0" and c.sufficient) or last:
            return c
        await next_iteration(ctx, world, bundle, root, c, agent_data)
