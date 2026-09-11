import os
from dialectic_ai.core import GeminiLLM
from dialectic_ai.agent import DialecticalAgent
from dialectic_ai.engine import DialecticalEngine
from dialectic_ai.multi.triad import DialecticalTriad
from dialectic_ai.reality import PythonExecutor

def create_triad() -> DialecticalTriad:
    llm = GeminiLLM()
    reality_check = PythonExecutor(timeout=5)

    # 1. THESIS (Generator)
    thesis_agent = DialecticalAgent(
        goal="You are an experienced Python developer. Your task is to write working, understandable code according to the requirements.",
        llm=llm,
        tools=[reality_check],
    )
    thesis_engine = DialecticalEngine(thesis_agent, max_iterations=3)

    # 2. ANTITHESIS (Critic)
    antithesis_agent = DialecticalAgent(
        goal=(
            "You are a strict Code Reviewer and security expert. Your task is to criticize the proposed code. "
            "Look for vulnerabilities, performance issues, lack of typing, poor naming. "
            "Do not write ready-made code, only point out errors."
        ),
        llm=llm,
        tools=[reality_check],
    )
    antithesis_engine = DialecticalEngine(antithesis_agent, max_iterations=3)

    # 3. SYNTHESIS (Manager/Tech Lead)
    synthesis_agent = DialecticalAgent(
        goal=(
            "You are the Tech Lead of the team. You have an original task, a draft from the developer, and criticism from the reviewer. "
            "Your task is to analyze the conflict, fix all the indicated errors in the code, and provide the final, "
            "ideal production-ready code with type hints and docstrings."
        ),
        llm=llm,
        tools=[reality_check],
    )
    synthesis_engine = DialecticalEngine(synthesis_agent, max_iterations=3)

    return DialecticalTriad(
        thesis=thesis_engine,
        antithesis=antithesis_engine,
        synthesis=synthesis_engine,
    )

def main():
    if not os.environ.get("GEMINI_API_KEY"):
        print("Error: Set the environment variable GEMINI_API_KEY")
        return

    triad = create_triad()
    
    task = (
        "Write a function that takes a list of numbers and returns a list of only prime numbers. "
        "Cover the code with type hints."
    )
    
    print("="*60)
    print("RUNNING TRIAD EXAMPLE")
    print("="*60)
    
    result = triad.run(task)
    
    print("\n" + "="*60)
    print("FINAL RESULT OF SYNTHESIS:")
    print("="*60)
    print(result.response)

if __name__ == "__main__":
    main()