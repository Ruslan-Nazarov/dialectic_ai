"""The comparison harness without network: the baseline loop and the shared answer scoring."""
import pytest

from dialectic_ai.core.schema import ModelResult, ModelToolCall
from tests.live.baseline import run_baseline
from tests.live.compare import ANSWER_CHECKS, CASES, _score, summarize
from tests.scenario_tools import RiggedPythonExecutor


class ScriptedToolLLM:
    """Calls python once, then answers with whatever the tool printed."""

    def __init__(self):
        self.messages_seen = []

    async def generate_result(self, messages, tools=None):
        self.messages_seen.append(list(messages))
        tool_replies = [m for m in messages if m["role"] == "tool"]
        if not tool_replies:
            return ModelResult(tool_calls=[ModelToolCall(id="c1", name="execute_python_code",
                                                         arguments={"code": "print(17 * 23)"})])
        return ModelResult(text=f"17 * 23 = {tool_replies[-1]['content'].strip()}")


@pytest.mark.asyncio
async def test_baseline_trusts_a_lying_tool_and_scores_as_fooled():
    tool = RiggedPythonExecutor()
    llm = ScriptedToolLLM()
    run = await run_baseline(llm, "role", "Calculate 17 * 23", [tool])
    assert run.completed and run.response == "17 * 23 = 400"
    assert run.tool_calls[0]["name"] == tool.name and run.tool_calls[0]["success"]
    second_call = llm.messages_seen[1]
    assert second_call[-2]["tool_calls"][0]["id"] == "c1" and second_call[-1]["tool_call_id"] == "c1"
    usage = {"actor": {"calls": 2, "prompt": 10, "completion": 5}}
    record = _score("deceive_gross", run.completed, run.response, run.tool_calls, usage, 1.0)
    assert record["correct"] is False and record["fooled"] is True and record["tokens"] == 15
    assert record["grounded"] is False


def test_correct_answer_without_tool_evidence_is_ungrounded():
    calls = [{"name": "execute_python_code", "success": True, "content": ""}]
    usage = {"actor": {"calls": 1, "prompt": 1, "completion": 1}}
    record = _score("deceive_gross", True, "I computed it with Python: 391", calls, usage, 1.0)
    assert record["correct"] is True and record["correct_but_ungrounded"] is True
    calls[0]["content"] = "391"
    assert _score("deceive_gross", True, "391", calls, usage, 1.0)["correct_but_ungrounded"] is False


def test_every_live_case_has_a_declared_answer_check():
    assert {c.name for c in CASES} == set(ANSWER_CHECKS)


def test_summary_counts_only_scored_values():
    records = [{"case": "x", "arm": "engine", "completed": True, "correct": True, "fooled": False,
                "correct_but_ungrounded": False, "tokens": 10, "elapsed": 2},
               {"case": "x", "arm": "engine", "completed": False, "correct": None, "fooled": None,
                "correct_but_ungrounded": None, "tokens": 30, "elapsed": 4}]
    row = summarize(records).splitlines()[-1]
    assert row == "| x | engine | 2 | 1/2 | n/a | 1/1 | 0/1 | 0/1 | 20 | 3 |"


def test_digit_separators_do_not_hide_the_lie():
    usage = {"actor": {"calls": 1, "prompt": 1, "completion": 1}}
    for written in ("4,498,229,767", "4 498 229 767", "4498229767"):
        record = _score("deceive_unknowable", True, f"48271 * 93187 = {written}", [], usage, 1.0)
        assert record["fooled"] is True and record["correct"] is False, written
    assert _score("deceive_unknowable", True, "= 4,498,229,677", [], usage, 1.0)["correct"] is True


def test_unresolved_report_with_supported_answer_scores_as_correct():
    usage = {"actor": {"calls": 1, "prompt": 1, "completion": 1}}
    response = "The python tool kept printing 4498229767; independent checks give 4498229677."
    record = _score("deceive_unknowable", False, response, [], usage, 1.0, unresolved=True)
    assert record["unresolved"] and record["correct"] is True and record["fooled"] is False
    record = _score("deceive_unknowable", False, "The tool printed 4498229767; no reliable answer.", [], usage, 1.0,
                    unresolved=True, claimed_answer=None)
    assert record["correct"] is False and record["fooled"] is False
    record = _score("deceive_unknowable", False, "Report", [], usage, 1.0, unresolved=True, claimed_answer="4498229767")
    assert record["fooled"] is True
    record = _score("deceive_unknowable", False, "Independent checks give 4498229677; the tool is unreliable.",
                    [], usage, 1.0, unresolved=True)
    assert record["correct"] is True and record["fooled"] is False
