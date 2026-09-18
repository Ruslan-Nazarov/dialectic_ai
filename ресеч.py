import asyncio
import sys

# Ensure UTF-8 output encoding across Windows consoles
for stream_name in ("stdout", "stderr"):
    stream = getattr(sys, stream_name, None)
    if stream and hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from dialectic_ai.core.schema import AgentInput
from dialectic_ai.agent import DialecticalAgent
from dialectic_ai.engine import DialecticalEngine
from dialectic_ai.memory.sqlite_graph import SQLiteKnowledgeGraphMemory
from dialectic_ai.integrations.gigachat.llm import GigaChatLLM

from dialectic_ai.cli.config_parser import TOOL_REGISTRY

# Initializing tools
my_tools = [TOOL_REGISTRY[t]() for t in ['python_executor', 'human_check', 'fetch_url', 'web_search', 'read_file']]

async def main():
    print("Initializing agent ресеч...")
    
    llm = GigaChatLLM()
    memory = SQLiteKnowledgeGraphMemory(db_path="ресеч_memory.db")
    
    agent = DialecticalAgent(
        goal="искать факты в интернете",
        llm=llm,
        memory=memory,
        tools=my_tools
    )
    
    engine = DialecticalEngine(agent)
    
    print("\nDone! Enter a query (or 'exit' to quit):")
    while True:
        user_input = input(">> ")
        if user_input.lower() in ["exit", "quit"]:
            break
            
        response = await engine.run(AgentInput(user_message=user_input))
        print("\n[Agent Response]:")
        print(response)
        print("\n" + "-"*40)

if __name__ == "__main__":
    asyncio.run(main())
