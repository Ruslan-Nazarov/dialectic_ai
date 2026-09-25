"""Local revision (architecture 5.2): data the agent met that does not fit the world changes only the part
of the world it concerns -- one new iteration (A 4.6) of the bundle holding that part; what rests on that
bundle is recomputed only when it is touched. The old version stays; the new one gets the next number."""
from datetime import datetime, timezone
from typing import Optional

from dialectic_world.adapter.adapter import WorldFit
from dialectic_world.builder.blocks import Context, compare
from dialectic_world.builder.build import develop_from_contradiction, develop_from_opposite
from dialectic_world.builder.bundle import run_bundle
from dialectic_world.world.model import Opposite, Revision, World
from dialectic_world.world.store import WorldStore

ORDER = ["p0", "opposite", "contradiction"]


def _bundle_of(world: World, pid: str) -> str:
    p = world.get(pid)
    if p.role == "p0":
        return "p0"
    if p.role in ("contradiction", "resolution"):
        return "contradiction"
    return p.bundle or "p0"


def affected_area(world: World, named: list[str]) -> list[str]:
    """The named processes and everything that flows from them (derived_from, parent_id)."""
    area = set(named)
    grew = True
    while grew:
        grew = False
        for p in world.processes.values():
            if p.id not in area and (area & set(p.derived_from) or p.parent_id in area):
                area.add(p.id)
                grew = True
    return sorted(area)


async def revise_world(ctx: Context, world: World, fit: WorldFit, agent_data: str,
                       store: Optional[WorldStore] = None) -> Optional[World]:
    named = [pid for pid in fit.process_ids if pid in world.processes]
    if not named:
        ctx.trace.event("revision_skipped", reason="the agent named no process of the world", note=fit.note)
        return None
    new = world.model_copy(deep=True)
    new.version, new.parent_version = world.version + 1, world.version
    new.created_at = datetime.now(timezone.utc).isoformat()
    bundle = min((_bundle_of(new, pid) for pid in named), key=ORDER.index)
    area = affected_area(new, named)
    data = f"{agent_data}\nЧто не укладывается: {fit.note}".strip()
    ctx.carry = f"Мир области пересматривается: новые данные не укладываются в него. {fit.note}"
    ctx.trace.event("revision", bundle=bundle, named=named, area=area, data=data[:1000])

    root = new.get(new.bundles[bundle].root_id)
    it = new.last_iteration(bundle)
    it.comparison = await compare(ctx, new, bundle, root, it.n, last=False, agent_data=data)   # the plan (A 4.6)
    result = await run_bundle(ctx, new, bundle, root, agent_data=data, iterations=1)

    summary = f"новая итерация пучка {bundle}"
    if bundle == "p0":
        old = new.opposite.process_id if new.opposite else None
        still = old and new.get(old).status == "active" and old in new.last_iteration("p0").developing
        if result.opposite_id and result.opposite_id != old:
            new.opposite = Opposite(process_id=result.opposite_id, why_not_required=result.why_not_required)
            await develop_from_opposite(ctx, new)
            summary += "; противоположность изменилась — пересчитаны противоречие и разрешение"
        elif not still:
            new.status = "no_opposite"
            summary += "; прежняя противоположность убрана, новая не найдена"
    elif bundle == "opposite":
        await develop_from_contradiction(ctx, new, new_contradiction=True)
        summary += "; пересчитаны противоречие и разрешение"
    else:
        await develop_from_contradiction(ctx, new, new_contradiction=False)
        summary += "; пересчитано разрешение"
    new.revisions.append(Revision(at=new.created_at, trigger=data[:2000], affected=area, bundle=bundle, summary=summary))
    ctx.trace.event("world", status=new.status, version=new.version, summary=summary)
    if store:
        store.save(new)
    return new
