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
from dialectic_ai.agent.base import DialecticalAgent

@dialectical(
    origin="Weakness of LLM in self-criticism (sycophancy). One agent poorly breaks its own ideas.",
    contradiction="If the agent is alone, its 'Confrontation with reality' is limited. A true dialogue requires two subjects.",
    resolves="Initiates debates between three agents: Thesis, Antithesis (Critic), Synthesis (Judge).",
    generates="The highest level of dialectical reasoning. Minimization of hallucinations through cross-examination.",
    own_contradictions="Long, expensive (tokens). Agents can 'loop' on one argument.",
    layer=4,
)
class DialecticalDebateEngine(DialecticalObject):
    """
    Engine for organizing dialectical debates between agents.
    """
    def __init__(
        self,
        thesis_agent: DialecticalAgent,
        antithesis_agent: DialecticalAgent,
        synthesis_agent: DialecticalAgent,
        max_rounds: int = 1
    ):
        super().__init__()
        self.thesis = thesis_agent
        self.antithesis = antithesis_agent
        self.synthesis = synthesis_agent
        self.max_rounds = max_rounds

    async def run_debate(self, user_topic: str) -> str:
        # Simplified stub for demonstrating architecture
        # In reality, DialecticalEngine would be called here for each agent
        
        print(f"\n[DEBATES] Topic: {user_topic}")
        
        # 1. Thesis
        print(f"[{self.thesis.goal}] generates Thesis...")
        thesis_statement = f"Thesis on the topic '{user_topic}': This is a great idea because..."
        
        # 2. Antithesis
        print(f"[{self.antithesis.goal}] looks for contradictions (Antithesis)...")
        antithesis_statement = f"Critique of the Thesis: The idea will not work because it is vulnerable to..."
        
        # 3. Synthesis
        print(f"[{self.synthesis.goal}] forms Synthesis...")
        synthesis_statement = (
            f"Synthesis: Considering the thesis and the critique, the final decision: "
            f"let's implement the idea, but add protection against the vulnerability."
        )
        
        return synthesis_statement
