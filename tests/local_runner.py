"""
tests/local_runner.py

Lightweight local sandbox: runs a few hardcoded micro-scenarios against the
DialecticalEngine with cheap mock tools, so engine logic can be iterated on
without spending GAIA2-scale tokens or time.

Usage:
    python tests/local_runner.py
    python tests/local_runner.py --debug
"""
import argparse
import asyncio
import os
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from dotenv import load_dotenv

from dialectic_ai.agent.base import DialecticalAgent
from dialectic_ai.core.llm import BalancingLLM
from dialectic_ai.core.schema import AgentInput
from dialectic_ai.engine.executor import DialecticalEngine
from dialectic_ai.integrations.openai.llm import OpenAILLM
from mock_tools import MockCalculatorTool, MockNoteSaverTool, MockWeatherTool

SCENARIOS = [
    "What is the weather in Paris?",
    "Save a note: milk, bread, eggs",
    "Find out the weather in London and save it in a note.",
]


def build_llm() -> BalancingLLM:
    providers = []
    if os.getenv("GROQ_API_KEY"):
        providers.append(OpenAILLM(
            api_key=os.getenv("GROQ_API_KEY"),
            base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
        ))
    if os.getenv("CEREBRAS_API_KEY"):
        providers.append(OpenAILLM(
            api_key=os.getenv("CEREBRAS_API_KEY"),
            base_url=os.getenv("CEREBRAS_BASE_URL", "https://api.cerebras.ai/v1"),
            model=os.getenv("CEREBRAS_MODEL", "gpt-oss-120b"),
        ))
    if not providers:
        raise RuntimeError("No LLM provider API key found in .env (GROQ_API_KEY / CEREBRAS_API_KEY).")
    return BalancingLLM(providers=providers)


async def run_scenario(engine: DialecticalEngine, message: str, index: int) -> None:
    print(f"\n{'#'*70}\n# SCENARIO {index}: {message}\n{'#'*70}")
    engine.agent.clear_history()
    output = await engine.run(AgentInput(user_message=message, session_id=f"sandbox-{index}"))
    print(f"\n  [Result] status={output.status}")
    print(f"  [Result] response={output.response}")
    if output.evidence:
        print(f"  [Result] evidence_used={len(output.evidence)}")


async def main(debug: bool) -> None:
    load_dotenv()

    tools = [MockWeatherTool(), MockCalculatorTool(), MockNoteSaverTool()]
    agent = DialecticalAgent(
        goal="You are a helpful assistant with access to weather, calculator, and note-saving tools.",
        llm=build_llm(),
        tools=tools,
    )
    engine = DialecticalEngine(agent, max_iterations=5, debug_mode=debug)

    for i, scenario in enumerate(SCENARIOS, start=1):
        await run_scenario(engine, scenario, i)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run local sandbox micro-scenarios against DialecticalEngine.")
    parser.add_argument("--debug", action="store_true", help="Pause after each LLM generation step.")
    args = parser.parse_args()
    asyncio.run(main(debug=args.debug))
