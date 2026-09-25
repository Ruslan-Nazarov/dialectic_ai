"""Zero-network protocol demonstration; output is explicitly simulation."""
import asyncio
from dialectic_ai.agent import DialecticalAgent
from dialectic_ai.core.schema import AgentInput
from dialectic_ai.engine import DialecticalEngine
from dialectic_ai.tools import web_search

async def main():
    engine = DialecticalEngine(DialecticalAgent("Demonstrate the protocol", tools=[web_search()]))
    for message in ["First protocol example", "Second isolated run"]:
        result = await engine.run(AgentInput(user_message=message))
        print(result.model_dump_json(indent=2))
        print("roadmaps:", len(engine.state._roadmaps), "observations:", len(engine.state.get_all_observations()))
        if result.status != "completed":
            raise RuntimeError(result.stop_reason)

if __name__ == "__main__":
    asyncio.run(main())
