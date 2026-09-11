import asyncio
from dialectic_ai.core.schema import AgentInput
from dialectic_ai.agent import DialecticalAgent
from dialectic_ai.engine import DialecticalEngine
from dialectic_ai.memory.sqlite_graph import SQLiteKnowledgeGraphMemory
from dialectic_ai.core.llm import FallbackLLM, MockLLM
from dialectic_ai.integrations.openai.llm import OpenAILLM
from dialectic_ai.integrations.gemini.llm import GeminiLLM
from dialectic_ai.integrations.web.tool import WebFetchCheck
import os

async def main():
    print("Initializing Test Researcher Agent...")
    
    # Check if we have real API keys, otherwise fallback to MockLLM for safe testing
    if os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("OPENROUTER_API_KEY") or os.getenv("GROQ_API_KEY"):
        print("Real API keys found, using FallbackLLM with real models.")
        providers = []
        if os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY") or os.getenv("GROQ_API_KEY"):
            providers.append(OpenAILLM())
        if os.getenv("GEMINI_API_KEY"):
            providers.append(GeminiLLM())
        llm = FallbackLLM(providers)
    else:
        print("No API keys found, using MockLLM for simulation.")
        llm = MockLLM([
            '{"thought": "I need to check the web for this query.", "tool_calls": [{"name": "fetch_url", "arguments": {"url": "https://example.com"}}], "response": ""}',
            '{"thought": "I found the information.", "tool_calls": [], "response": "Based on my research, example.com is a test domain established by IANA."}'
        ])
    
    # Initialize Memory and Tools
    memory = SQLiteKnowledgeGraphMemory(db_path="test_agent_memory.db")
    tools = [WebFetchCheck()]
    
    # Create the Agent
    agent = DialecticalAgent(
        goal="You are a general assistant and researcher. Your task is to help the user by finding information on the web and providing clear answers.",
        llm=llm,
        memory=memory,
        tools=tools
    )
    
    # Wrap agent in DialecticalEngine
    engine = DialecticalEngine(agent)
    
    print("\nReady! Let's test the agent with a sample query.")
    test_query = "Can you check example.com and tell me what it is for?"
    print(f"\n[User]: {test_query}")
    print("-" * 50)
    
    # Run the engine
    response = await engine.run(AgentInput(user_message=test_query))
    
    print("\n[Agent's Final Response]:")
    print(response.response)
    print("\n" + "="*50)
    print("Test Completed successfully!")

if __name__ == "__main__":
    asyncio.run(main())
