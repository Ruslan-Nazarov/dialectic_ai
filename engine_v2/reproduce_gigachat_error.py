import asyncio
import os
import sys

from dialectic_ai.core.schema import AgentInput
from dialectic_ai.core.agent import Agent
from dialectic_ai.integrations.gigachat import GigaChatLLM
from dialectic_ai.engine.executor import DialecticalEngine

async def main():
    token = os.environ.get("GIGACHAT_CREDENTIALS")
    if not token:
        print("Please set GIGACHAT_CREDENTIALS")
        sys.exit(1)
        
    llm = GigaChatLLM(credentials=token)
    agent = Agent(
        name="TestAgent",
        description="A test agent",
        llm=llm,
        tools=[]
    )
    
    engine = DialecticalEngine(agent, max_iterations=5)
    print("Running engine with complex prompt...")
    # Complex query that forces reasoning and possible JSON truncation/formatting issues
    result = await engine.run(AgentInput(
        user_message="Разработай сложную архитектуру микросервисного приложения для стриминга видео. Опиши каждый компонент, паттерны и потоки данных."
    ))
    
    print("Result Status:", result.status)
    print("Result Stop Reason:", result.stop_reason)

if __name__ == "__main__":
    asyncio.run(main())
