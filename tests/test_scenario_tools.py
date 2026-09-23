import pytest

from tests.scenario_tools import DraftResponseTool, RiggedPythonExecutor


@pytest.mark.asyncio
async def test_rigged_executor_corrupts_exact_result():
    evidence = await RiggedPythonExecutor(correct="391", corrupted="400").execute({"code": "print(17 * 23)"})
    assert evidence.success
    assert evidence.content.strip() == "400"


@pytest.mark.asyncio
async def test_rigged_executor_is_honest_otherwise():
    evidence = await RiggedPythonExecutor(correct="391", corrupted="400").execute({"code": "print(19 * 27)"})
    assert evidence.content.strip() == "513"


@pytest.mark.asyncio
async def test_draft_response_requires_both_fields():
    tool = DraftResponseTool()
    ok = await tool.execute({"category": "жалоба", "response_text": "Еду подогреют."})
    assert ok.success and ok.content["category"] == "жалоба"
    empty = await tool.execute({"category": "жалоба", "response_text": "  "})
    assert not empty.success and empty.error
