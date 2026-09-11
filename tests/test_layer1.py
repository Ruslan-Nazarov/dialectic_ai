"""Test Layer 1: Memory and Agent."""
import sys
import os
import pytest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dialectic_ai.core import MockLLM, MemoryUpdate
from dialectic_ai.memory import KnowledgeGraphMemory, PersistentMemory
from dialectic_ai.agent import DialecticalAgent

@pytest.mark.asyncio
async def test_knowledge_graph_memory():
    mem = KnowledgeGraphMemory()
    mem.update([
        MemoryUpdate(concept="python_loops", status="struggling"),
        MemoryUpdate(concept="variables", status="learned"),
    ])
    context = mem.get_context()
    assert "python_loops: struggling" in context
    assert "variables: learned" in context

@pytest.mark.asyncio
async def test_persistent_memory():
    pmem = PersistentMemory(path="test_memory_state.json")
    pmem.update([MemoryUpdate(concept="indentation", status="struggling")])
    
    pmem2 = PersistentMemory(path="test_memory_state.json")
    context = pmem2.get_context()
    assert "indentation: struggling" in context
    
    if os.path.exists("test_memory_state.json"):
        os.remove("test_memory_state.json")

@pytest.mark.asyncio
async def test_dialectical_agent():
    mem = KnowledgeGraphMemory()
    agent = DialecticalAgent(
        goal="You are teaching Python. Ask leading questions, do not provide ready answers.",
        llm=MockLLM(),
        memory=mem,
    )
    prompt = agent.get_system_prompt()
    assert "You are teaching Python." in prompt


@pytest.mark.asyncio
async def test_conversation_memory():
    from dialectic_ai.memory.conversation import ConversationMemory
    from dialectic_ai.core.schema import AgentInput
    
    mem = ConversationMemory(max_turns=2)
    user_msg = AgentInput(user_message="Hello, I'm here.")
    parsed = {"response": "Hello! How can I help?"}
    
    mem.process_turn(user_msg, parsed)
    context = mem.get_context()
    
    assert "User: Hello, I'm here." in context
    assert "Assistant: Hello! How can I help?" in context