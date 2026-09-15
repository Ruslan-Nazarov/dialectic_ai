"""
dialectic_ai/multi/debate.py

DIALECTICAL DESCRIPTION:
  Origin: The Router simply redirects tasks from one agent to another.
    This is not dialectics, this is just a pipeline.
  Contradiction: We make one agent create a Thesis, Antithesis, and Synthesis. But LLM often
    agrees with itself (sycophancy). One agent poorly critiques its own ideas.
  Resolution: It separates roles. Agent A generates a solution (Thesis). Agent B tries to
    break it (Antithesis). Agent C takes their arguments and makes the final Synthesis.
  Outcome: A true dialectical Multi-Agent. A sharp increase in the quality of responses
    in complex tasks (for example, code architecture).
  Own contradictions: It spends 3 times more tokens and time. It can enter an
    infinite cycle of argument if the number of iterations (rounds) is not limited.
"""
import asyncio
from dialectic_ai.core.dialectical import dialectical, DialecticalObject
from dialectic_ai.core.schema import AgentInput
from dialectic_ai.agent.base import DialecticalAgent
from dialectic_ai.engine.executor import DialecticalEngine
from dialectic_ai.multi.protocol import AgentResult, DialecticalResolution


@dialectical(
    origin="Weakness of LLM in self-criticism (sycophancy). One agent poorly breaks its own ideas.",
    contradiction="If the agent is alone, its 'Confrontation with reality' is limited. A true dialogue requires two subjects.",
    resolves="Runs a real Simplest-process -> Development -> Opposite-process -> Contradiction -> Leap "
             "cycle across three agents: Thesis names and develops the simplest process, Antithesis is "
             "required to name a process that does not need the simplest one to exist (not merely an "
             "alternative practice), Synthesis states the contradiction explicitly and resolves it by a leap.",
    generates="The highest level of dialectical reasoning. Minimization of hallucinations through cross-examination.",
    own_contradictions="Long, expensive (tokens). Agents can 'loop' on one argument. The Antithesis agent "
                       "may still produce a mere alternative practice instead of a genuine opposite process; "
                       "nothing currently verifies the distinction other than the prompt's instruction.",
    layer=4,
    simplest_process="One agent proposing and developing a solution to the task (Thesis) from abstract to concrete.",
    opposite_process="A process that solves (or dissolves) the task without ever needing the Thesis's "
                     "simplest process — found by a second agent (Antithesis) reasoning independently, "
                     "not by critiquing the Thesis's text.",
)
class DialecticalDebateEngine(DialecticalObject):
    """
    Engine for organizing dialectical debates between agents.

    Each role is run through a real DialecticalEngine (Thesis and Antithesis in
    parallel, then Synthesis), the same execution path used by DialecticalTriad —
    this class differs from the Triad in the *content* of what each role is
    asked to produce (Rule 5's five elements), not in the plumbing.
    """
    def __init__(
        self,
        thesis_agent: DialecticalAgent,
        antithesis_agent: DialecticalAgent,
        synthesis_agent: DialecticalAgent,
        max_rounds: int = 1,
        timeout: float = 60.0,
    ):
        super().__init__()
        self.thesis = thesis_agent
        self.antithesis = antithesis_agent
        self.synthesis = synthesis_agent
        self.max_rounds = max_rounds
        self.timeout = timeout

    async def run_debate(self, user_topic: str, session_id: str = "default") -> AgentResult:
        """
        Drives the topic through Simplest process -> Development -> Opposite process ->
        Contradiction -> Leap, using three independently-run agents.
        """
        print(f"\n[DEBATE] Topic: {user_topic}")

        thesis_engine = DialecticalEngine(self.thesis, max_iterations=self.max_rounds + 2)
        antithesis_engine = DialecticalEngine(self.antithesis, max_iterations=self.max_rounds + 2)

        thesis_prompt = (
            f"Task: {user_topic}\n\n"
            "Step 1 (Simplest process): Identify the simplest process connected to this task — one that "
            "is generative (the full solution can be approached by developing it) and that every part of "
            "your eventual solution will stay connected back to.\n"
            "Step 2 (Development): Develop that simplest process from abstract to concrete — each step "
            "of your plan should already be contained, in potential form, in the step before it. Use your "
            "hypothesis.plan_steps for this chain.\n"
            "Provide your concrete solution as the final response."
        )
        antithesis_prompt = (
            f"Task: {user_topic}\n\n"
            "Do NOT critique any specific existing solution and do NOT propose a mere alternative "
            "implementation/library/practice for the same need — that is a different, weaker move.\n"
            "Instead, find and develop a process that solves or dissolves this task WITHOUT ever needing "
            "the most obvious, simplest starting process most people would reach for. Your process's own "
            "development must not require that simplest process to exist at all.\n"
            "State in your decision field, in one sentence, which simplest process yours does not need, "
            "then develop your own process from abstract to concrete and give your solution as the final response."
        )

        thesis_input = AgentInput(user_message=thesis_prompt, session_id=session_id)
        antithesis_input = AgentInput(user_message=antithesis_prompt, session_id=session_id)

        try:
            thesis_output, antithesis_output = await asyncio.gather(
                asyncio.wait_for(thesis_engine.run(thesis_input), timeout=self.timeout),
                asyncio.wait_for(antithesis_engine.run(antithesis_input), timeout=self.timeout),
            )
        except asyncio.TimeoutError:
            return AgentResult(
                agent_name="debate_synthesis",
                response=f"[Error] Thesis or Antithesis exceeded the {self.timeout:.0f}s timeout.",
                success=False,
            )

        simplest_process = (thesis_output.hypothesis.assumption if thesis_output.hypothesis else thesis_output.decision) or thesis_output.decision
        opposite_process = (antithesis_output.hypothesis.assumption if antithesis_output.hypothesis else antithesis_output.decision) or antithesis_output.decision

        print(f"\n  [Debate] Thesis simplest process: {simplest_process[:120]}")
        print(f"  [Debate] Antithesis opposite process: {opposite_process[:120]}")

        synthesis_prompt = (
            f"Task: {user_topic}\n\n"
            f"Simplest process (Thesis) and its concrete solution:\n"
            f"- Simplest process: {simplest_process}\n"
            f"- Solution: {thesis_output.response}\n\n"
            f"Opposite process (Antithesis) and its concrete solution:\n"
            f"- Opposite process: {opposite_process}\n"
            f"- Solution: {antithesis_output.response}\n\n"
            "These two, taken together in the unity of their development, are your `contradiction`. Resolve "
            "it with your `leap`: either a process that replaces both, absorbing what each was developing "
            "toward into its own development, or a process that makes it possible for both to keep existing "
            "side by side until a later process replaces them. State your final answer as `response`."
        )
        synthesis_input = AgentInput(user_message=synthesis_prompt, session_id=session_id)
        synthesis_engine = DialecticalEngine(self.synthesis, max_iterations=self.max_rounds + 2)
        synthesis_output = await synthesis_engine.run(synthesis_input)

        # The base system prompt (agent/prompt_builder.py) already requires every agent -- Synthesis
        # included -- to fill opposite_process/contradiction/leap whenever it gives a `response`. No
        # regex extraction needed: read the same structural fields DialecticalEngine already populated.
        resolution = None
        if not synthesis_output.dialectical_resolution_missing:
            resolution = DialecticalResolution(
                simplest_process=simplest_process,
                opposite_process=opposite_process,
                contradiction=synthesis_output.contradiction,
                leap=synthesis_output.leap,
                resolution=synthesis_output.response,
            )

        return AgentResult(
            agent_name="debate_synthesis",
            response=synthesis_output.response,
            success=synthesis_output.is_final,
            metadata={"resolution": resolution} if resolution else {},
        )
