"""
Interactive agent creation wizard (CLI Wizard).
"""
import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

# Ensure UTF-8 output encoding across Windows consoles
for stream_name in ("stdout", "stderr"):
    stream = getattr(sys, stream_name, None)
    if stream and hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

from dialectic_ai.cli.config_parser import TOOL_REGISTRY


def _build_runtime_llm(llm_choice: str):
    """
    Constructs a live LLM instance for the one-off, creation-time design call.
    Separate from the boilerplate source text generated later for the agent's own
    runtime script — that text is generated regardless of whether this succeeds.
    """
    if llm_choice == "gemini":
        from dialectic_ai.integrations.gemini.llm import GeminiLLM
        return GeminiLLM()
    if llm_choice == "openai":
        from dialectic_ai.integrations.openai.llm import OpenAILLM
        return OpenAILLM()
    if llm_choice == "gigachat":
        from dialectic_ai.integrations.gigachat.llm import GigaChatLLM
        return GigaChatLLM()
    if llm_choice == "fallback":
        from dialectic_ai.core.llm import FallbackLLM
        from dialectic_ai.integrations.gemini.llm import GeminiLLM
        from dialectic_ai.integrations.openai.llm import OpenAILLM
        return FallbackLLM([GeminiLLM(), OpenAILLM()])
    return None  # mock, or unrecognized choice


def _maybe_refine_goal(llm_choice: str, name: str, goal: str, selected_tools: list, force_refine: bool = False) -> tuple:
    """
    Plain-language opt-in for the automatic dialectical design pass. On acceptance, runs
    DialecticalArchitect (Simplest -> Development -> Opposite -> Contradiction -> Leap) once,
    under the hood — the developer never has to know that vocabulary. Falls back to the raw
    goal, silently but visibly logged, on any failure (no LLM reachable, bad response, etc.).

    Returns (goal_to_use, design_log_markdown_or_None).
    """
    if llm_choice == "mock":
        return goal, None

    if force_refine:
        answer = "y"
    else:
        print("\nOptional: the connected AI model can automatically sharpen your goal before generating the agent.")
        answer = input("Refine the goal automatically now? [y/N]: ").strip().lower()
    
    if answer not in ("y", "yes"):
        return goal, None

    try:
        runtime_llm = _build_runtime_llm(llm_choice)
        if runtime_llm is None:
            return goal, None

        from dialectic_ai.cli.architect import DialecticalArchitect

        tool_descriptions = []
        for t in selected_tools:
            try:
                tool_descriptions.append(TOOL_REGISTRY[t]().description)
            except Exception:
                tool_descriptions.append(t)

        architect = DialecticalArchitect(runtime_llm)
        result = asyncio.run(architect.design(name, goal, tool_descriptions))
        print("Goal refined.")
        return result.refined_goal, architect.render_log_entry(name, goal, result)
    except Exception as e:
        print(f"[!] Could not refine the goal automatically ({e}); using your goal as written.")
        return goal, None


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
    print("   [5] GigaChat (requires GIGACHAT_AUTH_KEY)")

    llm_choice = input("Your choice (1-5) [default 1]: ").strip()
    llm = "gemini"
    if llm_choice == "2":
        llm = "openai"
    elif llm_choice == "3":
        llm = "mock"
    elif llm_choice == "4":
        llm = "fallback"
    elif llm_choice == "5":
        llm = "gigachat"

    goal, design_log = _maybe_refine_goal(llm, name, goal, selected_tools)

    # 5. Save format
    print("\n5. In what format to save the agent?")
    print("   [1] Python script (Recommended, easy to add your own code)")
    print("   [2] JSON config (For declarative launch)")
    format_choice = input("Your choice (1-2) [default 1]: ").strip()
    is_python = format_choice != "2"
    
    # 6. File name
    ext = ".py" if is_python else ".json"
    default_filename = f"{name.lower().replace(' ', '_')}{ext}"
    print("\n6. Saving.")
    filename = input(f"Enter file name [default {default_filename}]: ").strip()
    if not filename:
        filename = default_filename
    if not filename.endswith(ext):
        filename += ext

    generate_agent(
        name, goal, selected_tools, llm, is_python, filename,
        skip_refine=True, design_log_already_generated=design_log
    )

def generate_agent(
    name: str,
    goal: str,
    selected_tools: list,
    llm: str,
    is_python: bool,
    filename: str,
    force_refine: bool = False,
    design_log_already_generated: Optional[str] = None,
    skip_refine: bool = False,
) -> tuple[Path, str]:
    """Generates the agent files and returns (filepath, design_log_content)."""
    
    if skip_refine or design_log_already_generated is not None:
        design_log = design_log_already_generated
    else:
        goal, design_log = _maybe_refine_goal(llm, name, goal, selected_tools, force_refine=force_refine)

    # Forming config
    config = {
        "name": name,
        "goal": goal,
        "tools": selected_tools,
        "llm": llm,
        "max_iterations": 30
    }
    
    filepath = Path(filename)
    
    if is_python:
        # Generate Python boilerplate
        imports = ["import os", "from dialectic_ai.integrations.providers import build_llm"]
        tool_imports = ""
        if selected_tools:
            tool_imports = f"from dialectic_ai.cli.config_parser import TOOL_REGISTRY\n\n# Initializing tools\nmy_tools = [TOOL_REGISTRY[t]() for t in {selected_tools}]"
        else:
            tool_imports = "my_tools = []"
            
        llm_init = f"llm = build_llm(os.getenv('DIALECTIC_LLM_OVERRIDE') or {llm!r})"

        py_content = f'''import asyncio
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
{chr(10).join(imports)}

{tool_imports}

async def main():
    print({("Initializing agent " + name + "...")!r})

    {llm_init}

    agent = DialecticalAgent(
        goal={goal!r},
        llm=llm,
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
        print(f"[OK] Done! The agent has been successfully generated and saved to {filepath.absolute()}")
        print("============================================================")
        print("Now you can run it with the command:")
        print(f"  python {filepath.name}")
        
    else:
        # Generate JSON
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
            
        print("=" * 60)
        print(f"[OK] Done! The agent has been successfully generated and saved to {filepath.absolute()}")
        print("============================================================")
        print("Now you can run it with the command:")
        print(f"  python -m dialectic_ai.cli.main run {filepath.name}")

    if design_log:
        log_path = filepath.with_name(f"{filepath.stem}_development_log.md")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(design_log)
        print(f"Dialectical design log saved to {log_path.absolute()} "
              f"(readable by: python -m dialectic_ai.cli.main audit --config {filepath.name} --log {log_path.name})")

    print("\nGood luck with the dialectical synthesis!")
    
    return filepath, design_log
