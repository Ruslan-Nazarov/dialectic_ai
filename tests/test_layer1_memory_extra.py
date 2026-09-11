import os
import json
import pytest
from dialectic_ai.memory.persistent import PersistentMemory
from dialectic_ai.memory.sublation import SublationEngine
from dialectic_ai.core.schema import MemoryUpdate
from dialectic_ai.core.llm import MockLLM

def test_persistent_memory_save_load(tmp_path):
    file_path = tmp_path / "memory.json"
    mem = PersistentMemory(path=str(file_path))
    
    # Adding data
    mem.update([
        MemoryUpdate(concept="Python", status="learned", details="Language"),
        MemoryUpdate(concept="JS", status="unknown", details="Script")
    ])
    
    # Creating a new instance with the same file - should load history
    mem2 = PersistentMemory(path=str(file_path))
    assert len(mem2.inner.graph) == 2
    assert mem2.inner.graph["Python"] == "learned"
    assert mem2.inner.graph["JS"] == "unknown"

def test_persistent_memory_empty_file(tmp_path):
    file_path = tmp_path / "empty.json"
    mem = PersistentMemory(path=str(file_path))
    assert len(mem.inner.graph) == 0

@pytest.mark.asyncio
async def test_sublation_engine_sublate():
    llm = MockLLM()
    # MockLLM usually returns "Mock response"
    engine = SublationEngine(llm=llm)
    
    history = [
        {"role": "user", "content": "Thesis"},
        {"role": "agent", "content": "T-Response"}
    ]
    
    result = await engine.sublate(history)
    # MockLLM returning non-JSON will cause sublate to return error message or default
    assert isinstance(result, str)