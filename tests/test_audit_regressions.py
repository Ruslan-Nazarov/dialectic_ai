"""Regressions discovered by the research/technical audit; no live API calls."""
import asyncio
from pathlib import Path

import pytest

from dialectic_world import WorldSession, WorldStore, WorldAdapter
from dialectic_world.adapter.adapter import WorldFit
from dialectic_world.adapter.revise import revise_world
from dialectic_world.llm.base import LLM, FallbackLLM
from tests.test_adapter import built


async def test_contradiction_revision_retires_old_nodes_and_keeps_original():
    world, ctx, _ = await built()
    old_c, old_r = world.contradiction.process_id, world.resolution.process_id
    new = await revise_world(ctx, world, WorldFit(fits=False, process_ids=[old_c]), "new evidence")
    assert new.status == "built"
    assert new.contradiction.process_id != old_c
    assert new.get(old_c).status == new.get(old_r).status == "superseded"
    assert world.get(old_c).status == "active"
    assert old_c not in WorldAdapter(new, max_chars=100000).brief()


async def test_rejected_saved_revision_does_not_block_the_next_attempt(tmp_path):
    world, ctx, model = await built(store=WorldStore(tmp_path))
    session = WorldSession(world, ctx, WorldStore(tmp_path))
    pid = world.iterations[0].developing[0]
    model.opposite_at = None
    assert not await session.observe(WorldFit(fits=False, process_ids=[pid]), "no opposite")
    assert session.world.version == 1
    model.opposite_at = 1
    assert await session.observe(WorldFit(fits=False, process_ids=[pid]), "new evidence")
    assert session.world.version == 3 and session.world.parent_version == 1
    assert WorldStore(tmp_path).versions(world.domain) == [1, 2, 3]


async def test_rejected_in_memory_revision_keeps_parentage():
    world, ctx, model = await built()
    session = WorldSession(world, ctx)
    pid = world.iterations[0].developing[0]
    model.opposite_at = None
    assert not await session.observe(WorldFit(fits=False, process_ids=[pid]), "no opposite")
    model.opposite_at = 1
    assert await session.observe(WorldFit(fits=False, process_ids=[pid]), "new evidence")
    assert session.world.version == 3 and session.world.parent_version == 1


async def test_saved_version_is_immutable(tmp_path):
    store = WorldStore(tmp_path)
    world, _, _ = await built(store=store)
    path = store.path(world)
    saved = path.read_bytes()
    world.status = "failed"
    with pytest.raises(FileExistsError):
        store.save(world)
    assert path.read_bytes() == saved


async def test_repeated_independent_build_uses_a_new_version(tmp_path):
    store = WorldStore(tmp_path)
    first, _, _ = await built(store=store)
    original = store.path(first).read_bytes()
    second, _, _ = await built(store=store)
    assert second.version == 2 and second.parent_version is None
    assert store.path(first).read_bytes() == original
    assert store.versions(first.domain) == [1, 2]


async def test_mediation_is_a_valid_adopted_revision():
    world, ctx, model = await built()
    original = model.respond

    def respond(block, prompt):
        data = original(block, prompt)
        if block == "ResolveLeap":
            data["status"] = "CONTRADICTION_MEDIATED"
            data["leap"]["type"] = "MEDIATION"
        return data
    model.respond = respond
    session = WorldSession(world, ctx)
    assert await session.observe(WorldFit(fits=False, process_ids=[world.contradiction.process_id]), "evidence")
    assert session.world.status == "mediated"


def test_invalid_fit_metadata_does_not_crash_the_agent():
    assert WorldAdapter.parse_world_fit('{"world_fit":{"fits":"nonsense"}}') is None


async def test_brief_limit_covers_the_core_too():
    world, _, _ = await built()
    assert len(WorldAdapter(world, max_chars=40).brief()) == 40
    with pytest.raises(ValueError):
        WorldAdapter(world, max_chars=0)


class MeteredModel(LLM):
    async def _complete(self, messages):
        n = int(messages[0]["content"])
        await asyncio.sleep(0.01)
        return str(n), n, 1


@pytest.mark.parametrize("fallback", [False, True])
async def test_concurrent_calls_have_exact_local_usage(fallback):
    model = MeteredModel(model="metered")
    llm = FallbackLLM([model]) if fallback else model

    async def call(n):
        await llm.generate([{"role": "user", "content": str(n)}])
        return llm.last_call_usage
    assert await asyncio.gather(call(10), call(20), call(30)) == [(10, 1), (20, 1), (30, 1)]
    assert llm.usage.total == 63


def test_historical_briefs_match_frozen_treatments():
    from experiments.legacy_world import brief, load_world
    root = Path(__file__).resolve().parents[1]
    paths = {"nda": root / "experiments/grounding_vs_calibration/data/world_nda_v1.json",
             "control": root / "research_artifacts/legacy_v3/control_world_v1.json"}
    for name, path in paths.items():
        expected = (root / f"research_artifacts/legacy_v3/{name}_brief.txt").read_text(encoding="utf-8")
        assert brief(load_world(path)) == expected
    assert len(brief(load_world(paths["nda"]))) == 7717
    assert len(brief(load_world(paths["control"]))) == 7960


async def test_unknown_opposition_reference_is_reasked_as_form_error():
    from dialectic_world import Context, build_world
    from tests.fake import FakeModel
    model = FakeModel()
    model.overrides["CompareDevelopment"] = [{"status": "COMPARISON_COMPLETED",
        "opposition_candidates": [{"process_ref": "I99.P1", "not_yet_proven": True}]}]
    world = await build_world("domain", Context(llm=model))
    assert world.status == "built"
    assert "неизвестный process_ref" in model.calls("CompareDevelopment")[1]


async def test_trace_accounts_for_tool_request_and_final_answer():
    from dialectic_world import Context
    from dialectic_world.builder.blocks import ask

    class ToolModel(LLM):
        async def _complete(self, messages):
            if len(messages) == 1:
                return '{"tool":"lookup","args":{}}', 10, 2
            return '{"answer":"verified"}', 20, 3

    model = ToolModel(model="tool-test")
    ctx = Context(llm=model, tools={"lookup": ("fetch an observation", lambda: "observation")})
    assert await ask(ctx, "test", "task", lambda d: d["answer"]) == "verified"
    calls = [e for e in ctx.trace.events if e["kind"] == "block"]
    assert sum(sum(e["tokens"]) for e in calls) == model.usage.total == 35
    assert len({e["request_sha256"] for e in calls}) == 2
