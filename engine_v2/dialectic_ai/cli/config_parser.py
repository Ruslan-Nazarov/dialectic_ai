"""
Configuration parser for Declarative Agents (Layer 7)
"""
import json
from pathlib import Path

from dialectic_ai.agent import DialecticalAgent
from dialectic_ai.core.llm import FallbackLLM, MockLLM
from dialectic_ai.integrations.gemini.llm import GeminiLLM
from dialectic_ai.integrations.gigachat.llm import GigaChatLLM
from dialectic_ai.integrations.openai.llm import OpenAILLM
from dialectic_ai.reality import HumanRealityCheck, PythonExecutor, WebFetchCheck
from dialectic_ai.tools import read_file, web_search, write_file

TOOL_REGISTRY = {
    "python_executor": PythonExecutor,
    "human_check": HumanRealityCheck,
    "fetch_url": WebFetchCheck,
    "web_search": web_search,
    "read_file": read_file,
    "write_file": write_file,
}

def load_agent_from_config(config_path: str) -> DialecticalAgent:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file '{config_path}' not found.")
        
    with open(path, "r", encoding="utf-8") as f:
        # Attempting to parse as JSON. If YAML is added in the future, a fallback can be included.
        try:
            config = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON parsing error in file '{config_path}': {e}")
            
    # 1. Load LLM
    llm_name = config.get("llm", "mock").lower()
    from dialectic_ai.integrations.providers import build_llm
    llm = build_llm(llm_name)

    # 2. Load tools (Reality Checks)
    tools = []
    for tool_name in config.get("tools", []):
        tool_class = TOOL_REGISTRY.get(tool_name.lower())
        if not tool_class:
            raise ValueError(f"Unknown tool: '{tool_name}'. Available: {list(TOOL_REGISTRY.keys())}")
        if tool_name == "web_search" and llm_name != "mock":
            raise ValueError("web_search is a mock; use fetch_url for real pages")
        tools.append(tool_class())
        
    # 3. Assemble the agent
    goal = config.get("goal", "You are a helpful AI assistant.")
    # agent_name is parsed but DialecticalAgent has no .name field yet -- see CODE_REVIEW.md [SMELL]
    # agent_name = config.get("name", "DeclarativeAgent")
    
    agent = DialecticalAgent(
        goal=goal,
        llm=llm,
        tools=tools,
    )
    # Here we could set agent.name, but we currently do not have such a field in DialecticalAgent
    
    return agent
