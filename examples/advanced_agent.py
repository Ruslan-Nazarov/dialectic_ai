import sys
import asyncio
from pathlib import Path

# Adding the project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from dialectic_ai.agent import DialecticalAgent
from dialectic_ai.integrations.openai.llm import OpenAILLM
from dialectic_ai.memory.sqlite_graph import SQLiteKnowledgeGraphMemory
from dialectic_ai.engine import DialecticalEngine
from dialectic_ai.tools import web_search

from dialectic_ai.core.schema import AgentInput

async def main():
    print("=== Initializing Advanced Agent (DialecticAI 0.1) ===")
    
    # Initializing a new SQLite database
    db_path = "examples_memory.db"
    memory = SQLiteKnowledgeGraphMemory(db_path=db_path)
    
    # Note: dialectic_ai.tools.web_search is a MOCK -- it makes no real network
    # call and returns fixed, fabricated text (see tools/web_search.py). This
    # example demonstrates the tool-use/memory plumbing, not real news retrieval.
    agent = DialecticalAgent(
        goal="You are an AI reporter. Your task: find fresh news about AI and educate the user.",
        llm=OpenAILLM(),
        memory=memory,
        tools=[web_search()]
    )
    
    print("Agent successfully created! (Rule 1 is followed, @dialectical_tool works)")
    
    # Initializing the engine
    engine = DialecticalEngine(agent)
    
    print("\\n[Starting the loop]")
    response = await engine.run(AgentInput(user_message="Tell me what's new in the world of AI."))
    print("\\n=== Final response from the agent ===")
    print(response)
    print("\\n===============================")
    
    print("\nChecking Knowledge Graph (SQLite):")
    print(memory.get_context())

if __name__ == "__main__":
    asyncio.run(main())