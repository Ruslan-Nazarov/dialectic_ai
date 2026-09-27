"""Local revision: data the agent met that does not fit the world changes only the part of the world
it concerns. Simpler than under the old bundle scheme, because only P0 has multi-iteration development
here -- the opposite/contradiction/resolution are each a single process, recomputed directly rather
than through their own bundle of iterations. The old version stays; the new one gets the next number."""
from datetime import datetime, timezone
from typing import Optional

from dialectic_world.adapter.adapter import WorldFit
from dialectic_world.builder.blocks import Context, build_iteration, check_opposition, compare_development, \
    form_contradiction, resolve_leap
from dialectic_world.builder.build import _find_by_ref
from dialectic_world.world.model import Revision, World
from dialectic_world.world.store import WorldStore


def affected_area(world: World, named: list[str]) -> list[str]:
    """The named processes and everything that flows from them (derived_from)."""
    area = set(named)
    grew = True
    while grew:
        grew = False
        for p in world.processes.values():
            if p.id not in area and area & set(p.derived_from):
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
    area = affected_area(new, named)
    data = f"{agent_data}\nЧто не укладывается: {fit.note}".strip()
    ctx.trace.event("revision", named=named, area=area, data=data[:1000])

    touches_p0_development = any(new.get(pid).role in ("p0", "developing") for pid in area)
    summary = ""

    if touches_p0_development:
        n = new.iterations[-1].n + 1 if new.iterations else 1
        previous = new.iterations[-1] if new.iterations else None
        iteration = await build_iteration(ctx, new, n, previous, extra_context=data)
        new.iterations.append(iteration)
        comparison = await compare_development(ctx, new, extra_context=data)
        new.comparisons.append(comparison)
        confirmed = None
        if comparison.opposition_candidates:
            check = await check_opposition(ctx, new, comparison.opposition_candidates, extra_context=data)
            new.opposition_checks.append(check)
            confirmed = check.confirmed_opposites[0] if check.confirmed_opposites else None
        summary = f"новая итерация {n} развития P0"
        if confirmed is None:
            new.opposite, new.opposite_explanation = None, {}
            new.contradiction, new.resolution = None, None
            new.status = "no_opposite"
            summary += "; противоположность не (пере)найдена"
        else:
            new.opposite = _find_by_ref(new, confirmed["process_ref"])
            new.opposite_explanation = confirmed
            summary += f"; противоположность: {new.opposite.id}"
    elif area & {new.opposite.id if new.opposite else ""}:
        summary = "противоположный процесс затронут напрямую, без новой итерации P0"

    if new.opposite is not None and (touches_p0_development or
                                     (new.contradiction and new.contradiction.process_id in area) or
                                     (new.resolution and new.resolution.process_id in area)):
        contradiction = await form_contradiction(ctx, new, new.opposite, new.opposite_explanation, extra_context=data)
        if contradiction is None:
            new.status, new.contradiction, new.resolution = "failed", None, None
            summary += "; не удалось заново сформировать противоречие"
        else:
            new.contradiction = contradiction
            resolution = await resolve_leap(ctx, new, new.opposite, new.opposite_explanation, extra_context=data)
            new.resolution = resolution
            new.status = "built" if resolution and resolution.kind == "replacement" else \
                         "mediated" if resolution else "leap_not_found"
            summary += "; пересчитаны противоречие и разрешение"

    new.revisions.append(Revision(at=new.created_at, trigger=data[:2000], affected=area, summary=summary))
    ctx.trace.event("world", status=new.status, version=new.version, summary=summary)
    if store:
        store.save(new)
    return new
