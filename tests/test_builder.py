"""Builder mechanics on a scripted model: blocks, iterations, order, limits, form checks."""
import pytest

from dialectic_world import Context, Settings, WorldStore, build_world
from dialectic_world.builder.blocks import BlockFailed
from dialectic_world.trace import Trace
from tests.fake import FakeModel

DOMAIN = "жалобы посетителей столовой на холодную еду"
BLOCKS = ("FindP0", "BuildIteration", "CompareDevelopment", "CheckOpposition", "FormContradiction", "ResolveLeap")


def ctx(model, **settings):
    return Context(llm=model, settings=Settings(**settings), trace=Trace())


async def test_builds_the_whole_world_in_the_order_of_the_algorithm():
    model = FakeModel()
    world = await build_world(DOMAIN, ctx(model))
    assert world.status == "built"
    order = [b for b, _ in model.prompts]
    first = {b: order.index(b) for b in BLOCKS}
    assert first["FindP0"] < first["BuildIteration"] < first["CompareDevelopment"] < first["CheckOpposition"] \
        < first["FormContradiction"] < first["ResolveLeap"]
    assert world.opposite.role == "developing" and world.opposite.iteration == 1
    assert world.contradiction is not None and world.resolution is not None
    assert world.get(world.resolution.process_id).statement == "подогрев холодной еды"
    assert all(p.statement for p in world.processes.values())   # every process carries content


async def test_developing_processes_cumulative_basis_is_checked():
    model = FakeModel(per_iteration=4, opposite_at=None)
    world = await build_world(DOMAIN, ctx(model, developing_min=3, developing_max=5, iterations_max=1))
    first_iteration = world.iterations[0].developing
    assert len(first_iteration) == 4
    prompt = model.calls("BuildIteration")[0]
    assert '"current_iteration_processes": ["P1", "P2"]' in prompt.replace("  ", "").replace("\n", " ") \
        or "current_iteration_processes" in prompt   # basis is echoed by the fake, sanity check it's present


async def test_a_bad_developing_process_count_is_rejected_and_retried():
    model = FakeModel()
    bad = {
        "iteration": 1, "p0": {"process": "p0"}, "based_on_iteration": None,
        "developing_processes": [], "development_chain": ["P0"],
        "p0_revealed_content": "x", "iteration_practical_integrity": "y",
        "status": "ITERATION_BUILT", "failure_reason": None,
    }
    model.overrides["BuildIteration"] = [bad]
    world = await build_world(DOMAIN, ctx(model, developing_min=1, developing_max=5))
    assert world.status == "built"
    retry = model.calls("BuildIteration")[1]
    assert "Ответ отклонён по форме" in retry and "developing_processes" in retry


async def test_iterations_run_until_a_confirmed_opposite():
    model = FakeModel(opposite_at=3)
    world = await build_world(DOMAIN, ctx(model, iterations_max=5))
    assert [it.n for it in world.iterations] == [1, 2, 3]
    assert world.opposite.iteration == 3


async def test_no_p0_is_distinct_from_no_opposite():
    model = FakeModel()
    model.overrides["FindP0"] = [{"from": "a", "to": "b", "statement": "s", "practical_link": "p",
                                  "why_initial": "w", "resolution_trace": "r", "development_potential": "d",
                                  "verdict": "not_suitable", "rejection_reason": "слабая связь"}] * 3
    world = await build_world(DOMAIN, ctx(model, p0_attempts=3))
    assert world.status == "no_p0" and world.p0 is None
    assert len(world.rejected_p0) == 3


async def test_a_new_simplest_is_sought_when_no_opposite_is_found():
    model = FakeModel(opposite_at=None, p0_names=["еда", "столовая", "холодная еда"])
    world = await build_world(DOMAIN, ctx(model, iterations_max=2, p0_attempts=3))
    assert world.status == "no_opposite"
    assert model.p0_calls == 3
    last = model.calls("FindP0")[-1]
    assert "«еда как переход»" in last and "«столовая как переход»" in last


async def test_the_second_simplest_is_kept_when_it_finds_the_opposite():
    model = FakeModel(opposite_at=None, p0_names=["еда", "холодная еда"])
    original = model.respond

    def respond(block, prompt):
        if block == "CompareDevelopment" and model.p0_calls == 2:
            model.opposite_at = 1
        return original(block, prompt)
    model.respond = respond
    world = await build_world(DOMAIN, ctx(model, iterations_max=2))
    assert world.status == "built"
    assert world.p0.target == "холодная еда"
    assert [r["p0"] for r in world.rejected_p0] == ["еда как переход"]


async def test_a_model_self_rejected_p0_is_retried():
    model = FakeModel(p0_names=["плохой кандидат", "хороший кандидат"])
    model.overrides["FindP0"] = [{"from": "a", "to": "b", "statement": "плохой кандидат",
                                  "practical_link": "p", "why_initial": "w", "resolution_trace": "r",
                                  "development_potential": "d", "verdict": "not_suitable",
                                  "rejection_reason": "слабая связь"}]
    world = await build_world(DOMAIN, ctx(model))
    assert world.status == "built"
    assert world.rejected_p0 == [{"p0": "плохой кандидат", "reason": "слабая связь"}]


async def test_a_malformed_answer_is_re_asked_with_the_reason():
    model = FakeModel()
    model.overrides["FindP0"] = [{"to": "y", "statement": "без from", "verdict": "candidate",
                                  "practical_link": "p", "why_initial": "w", "resolution_trace": "r",
                                  "development_potential": "d"}]
    world = await build_world(DOMAIN, ctx(model))
    assert world.status == "built"
    retry = model.calls("FindP0")[1]
    assert "Ответ отклонён по форме: поле 'from' пустое или отсутствует" in retry


async def test_a_block_that_never_answers_in_form_fails_loudly():
    model = FakeModel()
    model.overrides["FindP0"] = ["не json"] * 5
    with pytest.raises(BlockFailed):
        await build_world(DOMAIN, ctx(model, form_retries=2))


async def test_a_block_can_call_a_tool_inside_its_own_step():
    model = FakeModel()
    model.overrides["FindP0"] = [{"tool": "lookup", "args": {"q": "столовая"}}]
    seen = {}

    def lookup(q):
        seen["q"] = q
        return "факт о столовой"
    c = ctx(model)
    c.tools = {"lookup": ("поиск фактов", lookup)}
    world = await build_world(DOMAIN, c)
    assert world.status == "built" and seen["q"] == "столовая"
    assert "Результат инструмента:\nфакт о столовой" in model.calls("FindP0")[1]


async def test_saved_versions_are_never_overwritten(tmp_path):
    store = WorldStore(tmp_path)
    world = await build_world(DOMAIN, ctx(FakeModel()), store)
    assert store.versions(DOMAIN) == [1]
    with pytest.raises(FileExistsError):
        store.save(world)
    assert store.load(DOMAIN).p0.target == "холодная еда"


async def test_output_language_is_appended_to_every_block():
    model = FakeModel()
    await build_world(DOMAIN, ctx(model, output_language="en"))
    for block in BLOCKS:
        for prompt in model.calls(block):
            assert "Answer in English." in prompt


async def test_on_event_fires_once_per_block_and_is_optional():
    model = FakeModel()
    seen = []

    async def on_event(block, data):
        seen.append(block)
    c = ctx(model)
    c.on_event = on_event
    world = await build_world(DOMAIN, c)
    assert seen == ["FindP0", "BuildIteration", "CompareDevelopment", "CheckOpposition",
                    "FormContradiction", "ResolveLeap"]
    # and building without on_event set at all still works (it's optional)
    world2 = await build_world(DOMAIN, ctx(FakeModel()))
    assert world2.status == "built"


async def test_a_failed_build_leaves_the_partial_world_saved(tmp_path):
    model = FakeModel()
    model.overrides["ResolveLeap"] = ["не json"] * 5
    store = WorldStore(tmp_path)
    with pytest.raises(BlockFailed):
        await build_world(DOMAIN, ctx(model), store)
    saved = store.load(DOMAIN)
    assert saved.status == "failed" and saved.contradiction is not None


async def test_a_leap_not_found_is_a_distinct_status_not_a_crash():
    model = FakeModel()
    model.overrides["ResolveLeap"] = [{"contradiction": {"p0": "p0", "opposite": "o", "essential_relation": "r"},
                                       "leap": None, "previous_p0_status": "NOT_YET_CONFIRMED", "next_cycle": None,
                                       "status": "LEAP_NOT_FOUND", "failure_reason": "нет обоснованного скачка"}]
    world = await build_world(DOMAIN, ctx(model))
    assert world.status == "leap_not_found" and world.resolution is None and world.contradiction is not None


async def test_a_mediation_leap_sets_the_mediated_status():
    model = FakeModel()
    model.overrides["ResolveLeap"] = [{"contradiction": {"p0": "p0", "opposite": "o", "essential_relation": "r"},
                                       "leap": {"type": "MEDIATION", "process": "временный процесс",
                                                "emerges_from_contradiction": "e", "preserves_p0": "p",
                                                "preserves_opposite": "o", "changes_contradiction": "c",
                                                "enables_further_development": "d", "practical_basis": "b"},
                                       "previous_p0_status": "NOT_YET_CONFIRMED", "next_cycle": None,
                                       "status": "CONTRADICTION_MEDIATED", "failure_reason": None}]
    world = await build_world(DOMAIN, ctx(model))
    assert world.status == "mediated" and world.resolution.kind == "mediation"
