"""Test Layer 2: Reality Check (RealityCheck / PythonExecutor)."""
import sys
import os
import pytest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dialectic_ai.reality import PythonExecutor
from dialectic_ai.agent import DialecticalAgent

@pytest.mark.asyncio
async def test_python_executor_success():
    executor = PythonExecutor(timeout=5)
    result = await executor.execute({"code": "for i in range(3):\n    print(i)"})
    assert result.success is True
    assert "0\n1\n2" in result.content.replace("\r\n", "\n")

@pytest.mark.asyncio
async def test_python_executor_error():
    executor = PythonExecutor(timeout=5)
    result = await executor.execute({"code": "for i in range(3):\nprint(i)"})
    assert result.success is False
    assert "IndentationError" in result.error

@pytest.mark.asyncio
async def test_python_executor_timeout():
    executor = PythonExecutor(timeout=1)
    result = await executor.execute({"code": "while True: pass"})
    assert result.success is False
    assert "Timeout" in result.error

@pytest.mark.asyncio
async def test_agent_with_tool_prompt():
    executor = PythonExecutor(timeout=5)
    agent = DialecticalAgent(
        goal="You are a Python tutor.",
        tools=[executor],
    )
    prompt = agent.get_system_prompt()
    assert "execute_python_code" in prompt