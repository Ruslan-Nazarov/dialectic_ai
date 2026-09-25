"""The adapter, the agent session and the local revision of the world."""
import json

from dialectic_world import Context, Settings, WorldAdapter, WorldSession, WorldStore, build_world, run_agent
from dialectic_world.adapter.revise import affected_area, revise_world
from dialectic_world.adapter.adapter import WorldFit
from dialectic_world.llm import ScriptedLLM
from dialectic_world.trace import Trace
from tests.fake import FakeModel

DOMAIN = "жалобы посетителей столовой на холодную еду"


async def built(store=None, **fake):
    model = FakeModel(**fake)
    c = Context(llm=model, settings=Settings(), trace=Trace())
    return await build_world(DOMAIN, c, store), c, model


async def test_the_brief_holds_the_whole_world_with_process_ids():
    world, _, _ = await built()
    brief = WorldAdapter(world).brief()
    for text in ("Простейший процесс P0: [P0]", "Противоположный процесс:", "Противоречие:", "Разрешение (replacement)",
                 "Развитие P0:", "Развитие противоположного:", "Развитие противоречия:"):
        assert text in brief, text


async def test_the_brief_keeps_the_core_and_cuts_internal_processes_first():
    world, _, _ = await built()
    full = WorldAdapter(world, max_chars=10**6).brief()
    internals_start = full.index("  · ")
    short = WorldAdapter(world, max_chars=internals_start).brief()
    assert "·" not in short and "Развитие противоречия:" in short
    tiny = WorldAdapter(world, max_chars=10).brief()                  # the core is never cut
    for text in ("Простейший процесс P0", "Противоположный процесс", "Противоречие", "Разрешение"):
        assert text in tiny


def test_the_world_fit_mark_is_read_from_json_or_a_last_line():
    assert WorldAdapter.parse_world_fit('{"answer": "x", "world_fit": {"fits": false, "process_ids": ["P1"], "note": "n"}}') \
        == WorldFit(fits=False, process_ids=["P1"], note="n")
    assert WorldAdapter.parse_world_fit('Ответ такой.\nWORLD_FIT: {"fits": true, "process_ids": []}').fits is True
    assert WorldAdapter.parse_world_fit("без пометки") is None


async def test_a_revision_changes_only_the_bundle_the_data_concerns(tmp_path):
    store = WorldStore(tmp_path)
    world, c, model = await built(store)
    target = world.last_iteration("contradiction").developing[0]
    before_p0 = {pid: p.model_dump() for pid, p in world.processes.items() if p.bundle == "p0" or p.role == "p0"}
    calls_before = len(model.prompts)
    new = await revise_world(c, world, WorldFit(fits=False, process_ids=[target], note="не так"), "письмо: ...", store)
    assert new.version == 2 and new.parent_version == 1 and store.versions(DOMAIN) == [1, 2]
    # P0's bundle, the opposite and the contradiction are untouched; one new iteration of the contradiction's
    # bundle and a new resolution.
    assert {pid: p.model_dump() for pid, p in new.processes.items() if p.bundle == "p0" or p.role == "p0"} == before_p0
    assert new.opposite == world.opposite and new.contradiction == world.contradiction
    assert len(new.bundles["contradiction"].iterations) == len(world.bundles["contradiction"].iterations) + 1
    assert new.resolution.process_id != world.resolution.process_id
    blocks = [b for b, _ in model.prompts[calls_before:]]
    assert "FindP0" not in blocks and "Contradiction" not in blocks and blocks[-1] == "Resolve"
    assert all("письмо: ..." in p for b, p in model.prompts[calls_before:] if b in ("Compare", "NextDeveloping"))
    assert new.revisions[-1].bundle == "contradiction"
    assert store.load(DOMAIN, 1).version == 1                       # the old version stays


async def test_a_revision_in_p0s_bundle_that_moves_the_opposite_rebuilds_what_rests_on_it():
    world, c, model = await built()
    original = model.respond

    def respond(block, prompt):
        answer = original(block, prompt)
        if block == "Compare" and "противоположный процесс (п. 4.8" in prompt and "Новые данные от агента" in prompt:
            from tests.fake import developing_ids
            answer["opposite_id"] = developing_ids(prompt)[0]
            answer["next_variant"] = 1
        return answer
    model.respond = respond
    named = world.last_iteration("p0").developing[0]
    new = await revise_world(c, world, WorldFit(fits=False, process_ids=[named]), "данные")
    assert new.opposite.process_id != world.opposite.process_id
    assert new.contradiction.process_id != world.contradiction.process_id
    assert new.revisions[-1].bundle == "p0"


def test_the_affected_area_is_what_flows_from_the_named_processes():
    from dialectic_world.world.model import Process, World
    w = World(domain="d")
    for pid, derived, parent in (("P0", [], None), ("P1", ["P0"], None), ("P2", ["P1"], None), ("P3", ["P0"], None),
                                 ("I1", [], "P2")):
        w.add(Process(id=pid, source="a", target="b", statement=pid, role="developing", bundle="p0",
                      derived_from=derived, parent_id=parent))
    assert affected_area(w, ["P1"]) == ["I1", "P1", "P2"]


async def test_a_revision_needs_named_processes():
    world, c, _ = await built()
    assert await revise_world(c, world, WorldFit(fits=False, process_ids=["nope"], note="?"), "данные") is None
    assert c.trace.events[-1]["kind"] == "revision_skipped"


async def test_the_agent_acts_in_the_world_and_its_mark_triggers_a_revision_within_the_limit():
    world, c, model = await built()
    c.settings.revisions_per_session = 1
    session = WorldSession(world, c)
    named = world.last_iteration("contradiction").developing[0]
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
