"""
dialectic_ai/reality/human.py

DIALECTICAL DESCRIPTION:
  Origin: The agent may encounter an unsolvable contradiction when the software reality (PythonExecutor) does not provide an answer, and its own knowledge is insufficient.
  Contradiction: The agent must be autonomous, but complete autonomy in a complex task leads to endless hallucinations.
  Resolution: HumanRealityCheck makes the human the highest form of "Reality". The agent can delegate the question to a human.
  Outcome: Safe execution (human-in-the-loop) and assistance in deadlocks.
"""
from dialectic_ai.core.dialectical import dialectical
from dialectic_ai.core.schema import Evidence
from dialectic_ai.core.tool import ActionTool
import uuid
import asyncio


@dialectical(
    origin="Agents get stuck if they cannot solve the problem programmatically on their own",
    contradiction="The agent must be autonomous, but sometimes a human is necessary",
    resolves="Introduces a human into the control loop as a tool",
    generates="Human-in-the-loop: safe delegation of decisions to a human",
    own_contradictions="Synchronous `input()` blocks the flow. Asynchronous waiting (webhook/UI) will be required in the future",
    layer=2,
)
class HumanRealityCheck(ActionTool):
    """
    Tool for requesting help or confirmation from a human.
    """

    @property
    def name(self) -> str:
        return "ask_human"

    @property
    def description(self) -> str:
        return "Requests information, confirmation, or a solution from a human user via the console."

    @property
    def category(self) -> str:
        return "Human Interaction"

    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Question to the human."
                }
            },
            "required": ["question"]
        }

    async def execute(self, args: dict) -> Evidence:
        question = args.get("question", "")
        if not question:
            return Evidence(
                id=str(uuid.uuid4()),
                source=self.name,
                content="",
                tool_name=self.name,
                success=False,
                error="No question provided to the human",
            )
        
        print(f"\n[Agent is asking for help from a human] {question}")
        answer = await asyncio.to_thread(input, "Your answer to the agent: ")
        
        return Evidence(
            id=str(uuid.uuid4()),
            source=self.name,
            content=answer,
            tool_name=self.name,
            success=True,
        )