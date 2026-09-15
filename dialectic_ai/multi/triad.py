"""
dialectic_ai/multi/triad.py

DIALECTICAL DESCRIPTION:
  Origin: Linear pipelines (Task1 -> Task2 -> Task3) do not allow
    for finding fundamental errors. If Task1 fails, Task3 will produce a bad result.
  Contradiction: We want high-quality answers, but one agent (even with tools)
    often suffers from "tunnel vision" and does not see its conceptual errors.
  How it resolves: The "Triad" pattern (Thesis, Antithesis, Synthesis). 
    1. Thesis (Generator) proposes a solution.
    2. Antithesis (Critic) looks for flaws, vulnerabilities, edge cases.
    3. Synthesis (Manager) resolves the conflict by combining the best and eliminating the weaknesses.
  What it leads to: A deeper, structurally sound, and reliable solution to complex tasks
    (for example, writing production code or architectural documents).
"""
from dialectic_ai.core.dialectical import dialectical
from dialectic_ai.core.schema import AgentInput, AgentOutput
from dialectic_ai.engine.executor import DialecticalEngine
from dialectic_ai.multi.protocol import AgentResult


@dialectical(
    origin="Linear chains of agents pass the error of the first step all the way to the end",
    contradiction="An agent cannot objectively criticize its own answer (tunnel vision)",
    resolves="Separates roles: Generator (Thesis), Critic (Antithesis) and Judge (Synthesis)",
    generates="Architectural pattern of the Triad for solving complex analytical and coding tasks",
    own_contradictions="Requires calling 3 agents for each task — 3 times more expensive and longer. "
                       "Use only for critically important processes",
    layer=4,
    simplest_process="One agent proposing a solution to the task (Thesis).",
    opposite_process="An independently generated critical/alternative take (Antithesis) that does not "
                     "need the Thesis's specific solution to exist — it stands on its own critique of "
                     "the task.",
)
class DialecticalTriad:
    """
    Manages task execution through the clash of opposites.
    Consists of three engines: Thesis, Antithesis, Synthesis.
    """

    def __init__(
        self,
        thesis: DialecticalEngine,
        antithesis: DialecticalEngine,
        synthesis: DialecticalEngine,
    ):
        self.thesis = thesis
        self.antithesis = antithesis
        self.synthesis = synthesis

    async def run(self, task: str, session_id: str = "default") -> AgentResult:
        """Starts the full cycle of the Triad to solve the task."""
        print("\n" + "="*60)
        print(f"  [TRIAD] New task: {task}")
        print("="*60)

        print("\n  [Triad] Step 1 & 2: THESIS & ANTITHESIS (Independent parallel generation)...")
        import asyncio
        thesis_input = AgentInput(user_message=task, session_id=session_id)
        
        antithesis_prompt = (
            f"Original task: {task}\n\n"
            "Do NOT critique any specific existing solution and do NOT propose a mere alternative "
            "implementation/library/practice for the same need -- that is a weaker move than what is "
            "being asked here. Instead, independently develop a process that solves this task WITHOUT "
            "ever needing the most obvious, standard approach most developers would reach for first. "
            "Find edge cases, vulnerabilities, and failure modes the obvious approach would miss, and "
            "develop your own process to address them, from abstract to concrete.\n"
            "State in your decision field, in one sentence, which standard/obvious approach yours does "
            "not need, then give your concrete solution as the final response."
        )
        antithesis_input = AgentInput(user_message=antithesis_prompt, session_id=session_id)

        try:
            thesis_output, antithesis_output = await asyncio.gather(
                asyncio.wait_for(self.thesis.run(thesis_input), timeout=60.0),
                asyncio.wait_for(self.antithesis.run(antithesis_input), timeout=60.0)
            )
        except asyncio.TimeoutError:
            return AgentResult(
                agent_name="triad_synthesis",
                response="[Error] Thesis or Antithesis exceeded the 60 second timeout.",
                success=False
            )

        draft = thesis_output.response
        critique = antithesis_output.response

        # 3. SYNTHESIS (Judge/Manager)
        print("\n  [Triad] Step 3: SYNTHESIS (Conflict resolution and final result)...")
        synthesis_prompt = (
            f"Original task: {task}\n\n"
            f"Simplest process (Thesis) and its concrete solution:\n{draft}\n\n"
            f"Opposite process (Antithesis), independently developed without needing the Thesis's "
            f"approach to exist:\n{critique}\n\n"
            "These two, taken together in the unity of their development, are your `contradiction`. "
            "Resolve it with your `leap`: take what each was developing toward, correct whatever gap "
            "the opposite process's existence reveals in the simplest process, and provide the ideal, "
            "final result as your `response`."
        )
        synthesis_input = AgentInput(user_message=synthesis_prompt, session_id=session_id)
        synthesis_output: AgentOutput = await self.synthesis.run(synthesis_input)
        final_result = synthesis_output.response

        return AgentResult(
            agent_name="triad_synthesis",
            response=final_result,
            success=synthesis_output.is_final,
        )
