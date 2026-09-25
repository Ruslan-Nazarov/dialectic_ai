"""Builder mechanics on a scripted model: blocks, bundles with iterations, order, limits, form checks."""
import pytest

from dialectic_world import Context, Settings, WorldStore, build_world
from dialectic_world.builder.blocks import BlockFailed
from dialectic_world.trace import Trace
from tests.fake import FakeModel

DOMAIN = "жалобы посетителей столовой на холодную еду"


def ctx(model, **settings):
    return Context(llm=model, settings=Settings(**settings), trace=Trace())


async def test_builds_the_whole_world_in_the_order_of_the_algorithm():
    model = FakeModel()
    world = await build_world(DOMAIN, ctx(model))
    assert world.status == "built"
    order = [b for b, _ in model.prompts]
    first = {b: order.index(b) for b in ("FindP0", "NextDeveloping", "Internals", "Compare", "Contradiction", "Resolve")}
    assert first["FindP0"] < first["NextDeveloping"] < first["Internals"] < first["Compare"] < first["Contradiction"] \
        < first["Resolve"]
    # The opposite is a developing process of P0's bundle; the three bundles exist.
    opp = world.get(world.opposite.process_id)
    assert opp.role == "developing" and opp.bundle == "p0"
    assert set(world.bundles) == {"p0", "opposite", "contradiction"}
    assert world.bundles["opposite"].root_id == opp.id
    assert world.bundles["contradiction"].root_id == world.contradiction.process_id
    assert world.get(world.resolution.process_id).statement == "подогрев холодной еды"
    # Every process is a transition (A 1.1).
    assert all(p.source and p.target for p in world.processes.values())


async def test_developing_processes_come_one_at_a_time_each_seeing_the_ones_before():
    model = FakeModel(per_iteration=4)
    world = await build_world(DOMAIN, ctx(model, developing_min=3, developing_max=5))
    first_iteration = world.bundles["p0"].iterations[0].developing
    assert len(first_iteration) == 4                  # the model's "more" decided, within 3..5
    prompts = model.calls("NextDeveloping")[:4]
    for k, prompt in enumerate(prompts):
        for earlier in first_iteration[:k]:
            assert f"[{earlier}]" in prompt           # A 4.2: each next one sees those already got
        for later in first_iteration[k:]:
            assert f"[{later}]" not in prompt


async def test_the_model_cannot_go_below_the_minimum_or_above_the_maximum():
    few = FakeModel(per_iteration=1)
    world = await build_world(DOMAIN, ctx(few, developing_min=3, developing_max=5))
    assert len(world.bundles["p0"].iterations[0].developing) == 3
    many = FakeModel(per_iteration=9)
    world = await build_world(DOMAIN, ctx(many, developing_min=3, developing_max=5))
    assert len(world.bundles["p0"].iterations[0].developing) == 5


async def test_internal_processes_are_built_in_parallel():
    model = FakeModel(delay=0.02)
    await build_world(DOMAIN, ctx(model))
    assert model.max_in_flight >= 3                   # the three developing processes' internals at once


async def test_iterations_run_until_the_opposite_and_follow_the_chosen_variant():
    model = FakeModel(opposite_at=3, next_variant=2, retire_first=True)
    world = await build_world(DOMAIN, ctx(model))
    its = world.bundles["p0"].iterations
    assert [it.n for it in its] == [1, 2, 3] and its[1].variant == 2
    retired = its[0].developing[0]
    assert world.get(retired).status == "retired" and retired not in its[1].developing
    # Variant 2 keeps the internal processes of the developing processes it keeps.
    kept = its[0].developing[1]
    assert its[1].internal[kept] == its[0].internal[kept]


async def test_variant_one_renews_internal_processes_linked_to_the_previous_ones():
    model = FakeModel(opposite_at=2, next_variant=1)
    world = await build_world(DOMAIN, ctx(model))
    first, second = world.bundles["p0"].iterations[:2]
    assert second.developing == first.developing
    for pid in first.developing:
        assert set(second.internal[pid]).isdisjoint(first.internal[pid])
        for iid in second.internal[pid]:
            assert world.get(iid).links_prev and set(world.get(iid).links_prev) <= set(first.internal[pid])


async def test_a_new_simplest_is_sought_when_no_opposite_is_found():
    model = FakeModel(opposite_at=None, p0_names=["еда", "столовая", "холодная еда"])
    world = await build_world(DOMAIN, ctx(model, iterations_max=2, p0_attempts=3))
    assert world.status == "no_opposite"
    assert model.p0_calls == 3
    last = model.calls("FindP0")[-1]
    assert "Уже отвергнуто: «еда как переход»" in last and "Уже отвергнуто: «столовая как переход»" in last


async def test_the_second_simplest_is_kept_when_its_bundle_reaches_the_opposite():
    model = FakeModel(opposite_at=None, p0_names=["еда", "холодная еда"])
    original = model.respond

    def respond(block, prompt):
        if block == "FindP0" and model.p0_calls == 1:
            model.opposite_at = 1
        return original(block, prompt)
    model.respond = respond
    world = await build_world(DOMAIN, ctx(model, iterations_max=2))
    assert world.status == "built" and world.p0.attempt == 2
    assert world.get("P0").target == "холодная еда"
    assert [r["p0"] for r in world.rejected_p0] == ["еда как переход"]


async def test_a_malformed_answer_is_re_asked_with_the_reason():
    model = FakeModel()
    model.overrides["NextDeveloping"] = [{"to": "y", "statement": "без from", "derived_from": ["P0"], "more": True}]
    world = await build_world(DOMAIN, ctx(model))
    assert world.status == "built"
    retry = model.calls("NextDeveloping")[1]
    assert "Ответ отклонён по форме: поле 'from' пустое или отсутствует" in retry


async def test_an_internal_process_cannot_be_the_opposite():
    model = FakeModel()
    original = model.respond
    state = {"done": False}

    def respond(block, prompt):
        answer = original(block, prompt)
        if block == "Compare" and not state["done"] and answer.get("opposite_id"):
            from tests.fake import internal_ids
            state["done"] = True
            answer["opposite_id"] = internal_ids(prompt)[0]
        return answer
    model.respond = respond
    world = await build_world(DOMAIN, ctx(model))
    assert world.get(world.opposite.process_id).role == "developing"
    assert any("внутренний процесс не может быть противоположным" in p for p in model.calls("Compare"))


async def test_a_block_that_never_answers_in_form_fails_loudly():
    model = FakeModel()
    model.overrides["FindP0"] = ["не json"] * 5
    with pytest.raises(BlockFailed):
        await build_world(DOMAIN, ctx(model, form_retries=2))


async def test_derived_from_must_name_existing_processes():
    model = FakeModel()
    model.overrides["NextDeveloping"] = [{"from": "a", "to": "b", "statement": "s", "derived_from": ["P999"], "more": True}]
    await build_world(DOMAIN, ctx(model))
    assert "'derived_from': нет таких процессов: ['P999']" in model.calls("NextDeveloping")[1]


async def test_each_block_receives_the_carry_of_the_block_before_it():
    model = FakeModel()
    await build_world(DOMAIN, ctx(model))
    assert "Передача от предыдущего блока: c0" in model.calls("NextDeveloping")[0]     # from FindP0
    assert "Передача от предыдущего блока: c1.0" in model.calls("NextDeveloping")[1]
    assert "Передача от предыдущего блока: c1.2" in model.calls("Compare")[0]


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
    assert store.load(DOMAIN).get("P0").target == "холодная еда"
