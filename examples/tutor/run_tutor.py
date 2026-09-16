"""
examples/tutor/run_tutor.py

DIALECTICAL DESCRIPTION:
  Origin: The Renaissance of the Python Tutor at a qualitatively new stage of the spiral
    (negation of negation). The Tutor gave rise to an abstract framework, and now the framework
    materializes the Tutor as a pure, modular artifact.
  Contradiction: Framework theory without practical application is barren;
    specific application without a framework is chaotic and unreliable.
  How it resolves: It brings together all layers of the DialecticAI framework:
    - Layer 0 (Core): GeminiLLM / OpenAILLM / MockLLM + DevelopmentLogger
    - Layer 1 (Agent & Memory): DialecticalAgent + KnowledgeGraphMemory
    - Layer 2 (Reality): PythonExecutor (syntax checking and code execution)
    - Layer 3 (Engine): DialecticalEngine (forced collision cycle)
    - Layer 5 (Observability): Logging each step in `tutor_trace.jsonl`
  What it leads to: The main demonstration of the project at the hackathon. You can simultaneously interact
    with the Tutor in the console and observe the thought process on the web dashboard.
  Its own contradictions: Limitations of the console context: multi-line code input
    requires a separator (empty line or EOF).
"""
import os
import sys
from pathlib import Path

# Non-English Windows consoles default to a narrow codepage (e.g. cp1251), not
# UTF-8 -- this script prints emoji, which crashes outright without this.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# Adding the project root to the module search path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dialectic_ai.core import (
    AgentInput,
    BaseLLM,
    MockLLM,
    GeminiLLM,
    OpenAILLM,
    DevelopmentLogger,
    print_dialectical_card,
)
from dialectic_ai.agent import DialecticalAgent
from dialectic_ai.memory import KnowledgeGraphMemory
from dialectic_ai.reality import PythonExecutor, HumanRealityCheck
from dialectic_ai.engine import DialecticalEngine


TUTOR_GOAL = """You are an experienced Socratic AI Tutor in the Python language.
Your mission:
1. DO NOT provide the student with ready-made solutions or corrected code.
2. Always analyze the student's code using the execute_python_code tool BEFORE responding.
3. When faced with an interpreter error, ask the student a precise, guiding question that helps them understand the cause of the error themselves.
4. Record the student's progress in knowledge_updates (concepts: python_indentation, for_loops, variables, functions; statuses: struggling, learning, mastered).
"""

# Queue of responses for the demo mode without API keys (MockLLM)
MOCK_TUTOR_RESPONSES = [
    # Response 1 to code with indentation error: invoking the tool
    """{
      "thought": "The student has submitted a code snippet. According to rule 3 of dialectics, I must check it with the interpreter.",
      "knowledge_updates": [],
      "tool_calls": [{"name": "execute_python_code", "args": {"code": "for i in range(3):\\nprint(i)"}}],
      "response": ""
    }""",
    # Response 2: synthesis after receiving IndentationError
    """{
      "thought": "Reality returned an IndentationError. The student did not consider the syntax of blocks in Python. Updating the knowledge graph and asking a Socratic question.",
      "knowledge_updates": [{"concept": "python_indentation", "status": "struggling"}],
      "tool_calls": [],
      "opposite_process": "Just telling the student the fixed code directly, without them running into the error themselves",
      "contradiction": "Handing over the fix teaches nothing; staying silent about a confirmed interpreter error abandons the student",
      "leap": "Report the real interpreter error, then ask a guiding question that lets the student find the fix themselves",
      "leap_type": "ask_only",
      "response": "I ran your code in a Python environment, and the interpreter returned an error:\\n`IndentationError: expected an indented block after 'for' statement`\\n\\nLook closely at the line `print(i)`. How does Python understand which commands should be executed inside the `for` loop?"
    }"""
]


def create_llm() -> BaseLLM:
    """Selects the most suitable LLM based on available keys."""
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if gemini_key:
        model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
        print(f"  [LLM] Using Google Gemini API ({model}).")
        return GeminiLLM(api_key=gemini_key, model=model)
    elif openai_key:
        print("  [LLM] Using OpenAI API.")
        return OpenAILLM(api_key=openai_key, model="gpt-4o-mini")
    else:
        print("  [LLM] API keys not found. Autonomous demo MockLLM is enabled.")
        return MockLLM(responses=MOCK_TUTOR_RESPONSES)


def create_tutor_engine(trace_file: str = "tutor_trace.jsonl", llm: BaseLLM = None) -> DialecticalEngine:
    """Creates and links all components of the Tutor."""
    llm = llm or create_llm()
    memory = KnowledgeGraphMemory(storage_path="tutor_memory.json")
    reality_check = PythonExecutor(timeout=5)
    human_check = HumanRealityCheck()
    logger = DevelopmentLogger(log_path="tutor_log.md", trace_path=trace_file)

    agent = DialecticalAgent(
        goal=TUTOR_GOAL,
        llm=llm,
        memory=memory,
        tools=[reality_check, human_check],
    )

    engine = DialecticalEngine(
        agent=agent,
        logger=logger,
        max_iterations=5,
    )

    return engine


def run_interactive_tutor():
    """Starts the dialog mode with the Tutor in the terminal."""
    print("\n" + "=" * 65)
    print("  🎓 DIALECTICAL AI TUTOR FOR PYTHON (DialecticAI)")
    print("=" * 65)
    print("  The Tutor uses Socratic dialogue and physically runs")
    print("  your code in a sandbox for reality checking.")
    print("  The web dashboard of traces is available with the command: python -m dialectic_ai.cli.main dashboard --trace tutor_trace.jsonl")
    print("  To exit, type: 'exit' or 'выход'\n")

    engine = create_tutor_engine("tutor_trace.jsonl")

    session_id = "student-interactive-01"

    while True:
        try:
            print("-" * 65)
            user_input = input("You (code or question): ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "выход", "q"):
                print("\n[Tutor] See you! Don't forget to check your hypotheses against reality.")
                break
            
            if user_input.startswith("/debug "):
                debug_code = user_input[7:].strip()
                try:
                    local_vars = {"engine": engine, "agent": engine.agent, "memory": engine.agent.memory}
                    exec(debug_code, globals(), local_vars)
                except Exception as e:
                    print(f"[Debug Error] {e}")
                continue

            import asyncio
            inp = AgentInput(user_message=user_input, session_id=session_id)
            out = asyncio.run(engine.run(inp))

            print("\n🎓 Tutor:")
            print(out.response)
            print()

        except KeyboardInterrupt:
            print("\nSession ended.")
            break


def main():
    """Entry point for standalone execution."""
    run_interactive_tutor()


if __name__ == "__main__":
    main()
