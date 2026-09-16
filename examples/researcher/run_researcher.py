import asyncio
import os
import sys

# Adding the project root to PYTHONPATH to run from any folder
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from dialectic_ai.core import GeminiLLM, MockLLM
from dialectic_ai.agent import DialecticalAgent
from dialectic_ai.engine import DialecticalEngine
from dialectic_ai.reality import WebFetchCheck

async def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        llm = GeminiLLM(api_key=api_key)
        print("Using Gemini API.")
    else:
        print("WARNING: GEMINI_API_KEY is not set. Using MockLLM.")
        llm = MockLLM(responses=[
            '{"thought": "I see a link. Requesting download.", "tool_calls": [{"name": "fetch_url", "args": {"url": "https://example.com"}}]}',
            '{"thought": "Received the page text.", "tool_calls": [], '
            '"opposite_process": "Answering from training-data knowledge about the domain without fetching it", '
            '"contradiction": "Training knowledge may be stale or wrong; the fetched page is the current ground truth", '
            '"leap": "Trust the fetched content over any prior assumption and report only what it says", '
            '"leap_type": "fully_resolved", '
            '"response": "The site says: Example Domain. This is a page for examples."}'
        ])

    web_tool = WebFetchCheck()
    
    agent = DialecticalAgent(
        goal=(
            "You are a Web Researcher. Your task is to extract facts from the internet. "
            "If the user gives you a URL or asks you to analyze something, "
            "you must use the fetch_url tool to download the page, "
            "and only respond to the user based on the facts from the page."
        ),
        llm=llm,
        tools=[web_tool]
    )
    
    engine = DialecticalEngine(agent, max_iterations=3)
    
    print("\n" + "="*60)
    print("RESEARCHER AGENT IS READY (WebFetchCheck)")
    print("="*60)
    
    topic = "https://example.com"
    print(f"\nUser: Analyze this site: {topic}")
    
    from dialectic_ai.core.schema import AgentInput
    result = await engine.run(AgentInput(user_message=topic))

    print("\n" + "="*60)
    print("FINAL RESPONSE OF THE RESEARCHER:")
    print("="*60)
    print(result.response)

if __name__ == "__main__":
    asyncio.run(main())