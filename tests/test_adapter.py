"""The adapter, the agent session and the local revision of the world."""
import json

from dialectic_world import Context, Settings, WorldAdapter, WorldSession, WorldStore, build_world, run_agent
from dialectic_world.adapter.revise import affected_area, revise_world
from dialectic_world.adapter.adapter import WorldFit
from dialectic_world.llm import ScriptedLLM
from dialectic_world.trace import Trace
from tests.fake import FakeModel

DOMAIN = "жалобы посетителей столовой на холодную еду"


async def built(store=None, settings=None, **fake):
    model = FakeModel(**fake)
    c = Context(llm=model, settings=settings or Settings(), trace=Trace())
    return await build_world(DOMAIN, c, store), c, model


async def test_the_brief_holds_the_whole_world_with_process_ids():
    world, _, _ = await built()
    brief = WorldAdapter(world).brief()
    for text in ("Простейший процесс P0: [P0]", "Противоположный процесс:", "Противоречие:", "Разрешение (replacement)",
                 "Развитие P0, итерация 1:"):
        assert text in brief, text


async def test_the_brief_keeps_the_core_and_cuts_older_iterations_first():
    world, _, _ = await built(settings=Settings(iterations_max=3), opposite_at=2)
    full = WorldAdapter(world, max_chars=10**6).brief()
    cut_point = full.index("Развитие P0, итерация 1:")     # the earliest iteration, listed last
    short = WorldAdapter(world, max_chars=cut_point).brief()
    assert "итерация 1:" not in short and "итерация 2:" in short
    tiny = WorldAdapter(world, max_chars=10).brief()        # the core is never cut
    for text in ("Простейший процесс P0", "Противоположный процесс", "Противоречие", "Разрешение"):
        assert text in tiny


def test_the_world_fit_mark_is_read_from_json_or_a_last_line():
    assert WorldAdapter.parse_world_fit('{"answer": "x", "world_fit": {"fits": false, "process_ids": ["P1"], "note": "n"}}') \
        == WorldFit(fits=False, process_ids=["P1"], note="n")
    assert WorldAdapter.parse_world_fit('Ответ такой.\nWORLD_FIT: {"fits": true, "process_ids": []}').fits is True
    assert WorldAdapter.parse_world_fit("без пометки") is None


def test_the_affected_area_is_what_flows_from_the_named_processes():
    from dialectic_world.world.model import Process, World
    w = World(domain="d")
    for pid, derived in (("P0", []), ("P1", ["P0"]), ("P2", ["P1"]), ("P3", ["P0"])):
        w.add(Process(id=pid, source="", target="", statement=pid, role="developing", derived_from=derived))
    assert affected_area(w, ["P1"]) == ["P1", "P2"]


async def test_a_revision_needs_named_processes():
    world, c, _ = await built()
    assert await revise_world(c, world, WorldFit(fits=False, process_ids=["nope"], note="?"), "данные") is None
    assert c.trace.events[-1]["kind"] == "revision_skipped"


async def test_a_revision_touching_p0s_development_runs_a_new_iteration_and_recomputes_downstream(tmp_path):
    store = WorldStore(tmp_path)
    world, c, model = await built(store)
    calls_before = len(model.prompts)
    named = world.iterations[0].developing[0]
    new = await revise_world(c, world, WorldFit(fits=False, process_ids=[named], note="не так"), "письмо: ...", store)
    assert new.version == 2 and new.parent_version == 1 and store.versions(DOMAIN) == [1, 2]
    assert len(new.iterations) == len(world.iterations) + 1
    assert new.contradiction.process_id != world.contradiction.process_id
    assert new.resolution.process_id != world.resolution.process_id
    blocks = [b for b, _ in model.prompts[calls_before:]]
    assert "FindP0" not in blocks and blocks[0] == "BuildIteration"
    assert all("письмо: ..." in p for b, p in model.prompts[calls_before:] if b == "BuildIteration")
    assert new.revisions[-1].summary
    assert store.load(DOMAIN, 1).version == 1                       # the old version stays


async def test_a_revision_that_loses_the_opposite_says_so():
    world, c, model = await built(opposite_at=1)
    original = model.respond

    def respond(block, prompt):
        if block == "CompareDevelopment" and "Что не укладывается" in prompt:
            model.opposite_at = None      # the new iteration no longer finds a candidate
        return original(block, prompt)
    model.respond = respond
    named = world.iterations[0].developing[0]
    new = await revise_world(c, world, WorldFit(fits=False, process_ids=[named], note="?"), "данные")
    assert new.status == "no_opposite" and new.opposite is None and new.contradiction is None


async def test_the_agent_acts_in_the_world_and_its_mark_triggers_a_revision_within_the_limit():
    world, c, model = await built()
    c.settings.revisions_per_session = 1
    session = WorldSession(world, c)
    named = world.iterations[0].developing[0]
    agent_prompts = []

    def agent(prompt):
        agent_prompts.append(prompt)
        if "Результат инструмента" not in prompt:
            return {"tool": "read_mail", "args": {"n": 1}}
        return {"answer": "дата 5 мая", "world_fit": {"fits": False, "process_ids": [named], "note": "не укладывается"}}
    tools = {"read_mail": ("читает письмо", lambda n: "письмо с двумя датами")}
    first = await run_agent(ScriptedLLM(agent), session, "поставь встречу", tools=tools)
    assert first.answer == "дата 5 мая" and first.revised and session.world.version == 2
    assert "КАРТИНА МИРА" in agent_prompts[0] and "[P0]" in agent_prompts[0]
    second = await run_agent(ScriptedLLM(agent), session, "ещё письмо", tools=tools)
    assert not second.revised and session.world.version == 2       # the limit holds
    assert "письмо с двумя датами" in json.dumps(session.world.revisions[0].trigger, ensure_ascii=False)


async def test_a_revision_that_the_session_rejects_is_not_adopted():
    world, c, model = await built()
    session = WorldSession(world, c)
    import dialectic_world.adapter.agent as agent_mod
    broken = world.model_copy(deep=True)
    broken.status, broken.version = "no_opposite", 2

    async def fake_revise(*args, **kwargs):
        return broken
    original = agent_mod.revise_world
    agent_mod.revise_world = fake_revise
    try:
        adopted = await session.observe(WorldFit(fits=False, process_ids=["P0"]), "д")
    finally:
        agent_mod.revise_world = original
    assert not adopted and session.world.version == 1
    assert c.trace.events[-1]["kind"] == "revision_not_adopted"
