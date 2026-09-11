"""
Interactive agent creation wizard (CLI Wizard).
"""
import json
import os
from pathlib import Path
from dialectic_ai.cli.config_parser import TOOL_REGISTRY

def run_interactive_creator():
    print("=" * 60)
    print("  DIALECTIC-AI AGENT CREATION WIZARD 🤖")
    print("=" * 60)
    
    print("\n[!] DEVELOPMENT PHILOSOPHY (Dialectical Method):")
    print("    1. Generative Beginning: Your agent should start with a simple and clear goal.")
    print("    2. Inheritance: Choose tools that organically stem from this goal.")
    print("    3. Confrontation with the World: The agent will test its hypotheses by invoking these tools.")
    print("    4. Transition Evaluation: Think critically — does the agent really need all these capabilities?")
    print("-" * 60)

    print("\nLet's create your new AI agent!\n")
    
    # 1. Agent name
    name = input("1. Come up with a name for the agent (e.g., WebResearcher): ").strip()
    if not name:
        name = "MyAgent"
        
    # 2. Role and goal
    print("\n2. Describe the agent's goal.")
    print("   Example: 'You are a Web Researcher. Your task is to gather facts from the internet.'")
    goal = input("Goal: ").strip()
    if not goal:
        goal = "You are a helpful AI assistant."
        
    # 3. Tools
    print("\n3. Choose the tools (Reality Checks) that the agent needs.")
    available_tools = list(TOOL_REGISTRY.keys())
    
    # Grouping by categories
    from collections import defaultdict
    from dialectic_ai.core.dialectical import DialecticalArchitectureError
    
    categories = defaultdict(list)
    for t in available_tools:
        try:
            tool_instance = TOOL_REGISTRY[t]()
            categories[tool_instance.category].append((t, tool_instance.description))
        except DialecticalArchitectureError as e:
            print(f"\n[WARNING] Tool '{t}' skipped due to architectural error (Rule 1).")
            # Print only the first line of the error (essence)
            print(f"  -> {str(e).splitlines()[0]}")
            continue
        
    idx = 1
    tool_map = {}
    for cat, tools in categories.items():
        print(f"\n   --- {cat} ---")
        for t, desc in tools:
            print(f"   [{idx}] {t:<15} - {desc}")
            tool_map[idx] = t
            idx += 1
            
    tools_input = input("\nEnter the numbers of the tools separated by commas (or leave blank if not needed): ").strip()
    selected_tools = []
    if tools_input:
        for i_str in tools_input.split(","):
            try:
                i = int(i_str.strip())
                if i in tool_map:
                    selected_tools.append(tool_map[i])
            except ValueError:
                pass
                
    # 4. LLM
    print("\n4. Which language model to use?")
    print("   [1] Gemini (requires GEMINI_API_KEY)")
    print("   [2] OpenAI / OpenRouter (requires OPENAI_API_KEY/OPENROUTER_API_KEY)")
    print("   [3] Mock (for local testing without internet)")
    print("   [4] Fallback Auto (Gemini -> OpenAI)")
    
    llm_choice = input("Your choice (1-4) [default 1]: ").strip()
    llm = "gemini"
    if llm_choice == "2":
        llm = "openai"
    elif llm_choice == "3":
        llm = "mock"
    elif llm_choice == "4":
        llm = "fallback"
        
    # Forming config
    config = {
        "name": name,
        "goal": goal,
        "tools": selected_tools,
        "llm": llm,
        "max_iterations": 3
    }
    
    # 5. Save format
    print("\n5. In what format to save the agent?")
    print("   [1] Python script (Recommended, easy to add your own code)")
    print("   [2] JSON config (For declarative launch)")
    format_choice = input("Your choice (1-2) [default 1]: ").strip()
    is_python = format_choice != "2"
    
    # 6. File name
    ext = ".py" if is_python else ".json"
    default_filename = f"{name.lower().replace(' ', '_')}{ext}"
    print(f"\n6. Saving.")
    filename = input(f"Enter file name [default {default_filename}]: ").strip()
    if not filename:
        filename = default_filename
    if not filename.endswith(ext):
        filename += ext
        
    filepath = Path(filename)
    
    if is_python:
        # Generate Python boilerplate
        imports = []
        if llm == "gemini":
            imports.append("from dialectic_ai.integrations.gemini.llm import GeminiLLM")
        elif llm == "openai":
            imports.append("from dialectic_ai.integrations.openai.llm import OpenAILLM")
        elif llm == "fallback":
            imports.append("from dialectic_ai.core.llm import FallbackLLM\nfrom dialectic_ai.integrations.gemini.llm import GeminiLLM\nfrom dialectic_ai.integrations.openai.llm import OpenAILLM")
        else:
            imports.append("from dialectic_ai.core.llm import MockLLM")
            
        tool_imports = ""
        if selected_tools:
            tool_imports = f"from dialectic_ai.cli.config_parser import TOOL_REGISTRY\n\n# Initializing tools\nmy_tools = [TOOL_REGISTRY[t]() for t in {selected_tools}]"
        else:
            tool_imports = "my_tools = []"
            
        llm_init = ""
        if llm == "gemini":
            llm_init = "llm = GeminiLLM()"
        elif llm == "openai":
            llm_init = "llm = OpenAILLM()"
        elif llm == "fallback":
            llm_init = "llm = FallbackLLM([GeminiLLM(), OpenAILLM()])"
        else:
            llm_init = "llm = MockLLM()"

        py_content = f'''import asyncio
from dialectic_ai.core.schema import AgentInput
from dialectic_ai.agent import DialecticalAgent
from dialectic_ai.engine import DialecticalEngine
from dialectic_ai.memory.sqlite_graph import SQLiteKnowledgeGraphMemory
{chr(10).join(imports)}

{tool_imports}

async def main():
    print("Initializing agent {name}...")
    
    {llm_init}
    memory = SQLiteKnowledgeGraphMemory(db_path="{name.lower()}_memory.db")
    
    agent = DialecticalAgent(
        goal="{goal}",
        llm=llm,
        memory=memory,
        tools=my_tools
    )
    
    engine = DialecticalEngine(agent)
    
    print("\\nDone! Enter a query (or 'exit' to quit):")
    while True:
        user_input = input(">> ")
        if user_input.lower() in ["exit", "quit"]:
            break
            
        response = await engine.run(AgentInput(user_message=user_input))
        print("\\n[Agent Response]:")
        print(response)
        print("\\n" + "-"*40)

if __name__ == "__main__":
    asyncio.run(main())
'''
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(py_content)
            
        print("=" * 60)
        print(f"✅ Done! The agent has been successfully generated and saved to {filepath.absolute()}")
        print("============================================================")
        print("Now you can run it with the command:")
        print(f"  python {filepath.name}")
        
    else:
        # Generate JSON
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
            
        print("=" * 60)
        print(f"✅ Done! The agent has been successfully generated and saved to {filepath.absolute()}")
        print("============================================================")
        print("Now you can run it with the command:")
        print(f"  python -m dialectic_ai.cli.main run {filepath.name}")

    print("\nGood luck with the dialectical synthesis! 🚀")