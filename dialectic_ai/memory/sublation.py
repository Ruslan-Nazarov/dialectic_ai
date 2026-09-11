"""
dialectic_ai/memory/sublation.py

DIALECTICAL DESCRIPTION:
  Origin: Dialogues grow. LLM has a finite context window (Context Window).
    If we simply delete old messages (sliding window), the agent forgets the context.
  Contradiction: We want to keep the entire history for quality responses, but we cannot
    physically store the entire history.
  How it resolves: The law of the transition of quantitative changes into qualitative ones (Sublation/Aufheben).
    SublationEngine takes a long raw history and compresses it into a compact "Synthesis",
    which replaces the original messages.
  What it leads to: Endless dialogues without context overflow.
"""
from dialectic_ai.core.dialectical import dialectical
from dialectic_ai.core.llm import BaseLLM


@dialectical(
    origin="Context Window Overflow in long dialogues",
    contradiction="The sliding window forgets the past; the complete history kills memory and is costly",
    resolves="Compression of past messages into a qualitative semantic synthesis (Aufheben)",
    generates="The ability to conduct eternal sessions without losing the general context",
    own_contradictions="LLM may lose important minor details during synthesis. Requires an additional API call",
    layer=1,
)
class SublationEngine:
    """
    Sublation Engine. Takes the raw message history and compresses it into a short summary (Synthesis) using LLM.
    """

    def __init__(self, llm: BaseLLM):
        self.llm = llm
        self.sublation_prompt = (
            "Your task is to compress the dialogue history (Sublation/Aufheben). "
            "Extract the main essence, solutions, and context from the provided messages. "
            "Remove filler, greetings, and irrelevant technical details. "
            "Synthesize this into one or two concise paragraphs. Return STRICTLY the synthesis text in JSON format: "
            '{"thought": "analysis", "response": "Synthesis text"}'
        )

    async def sublate(self, history: list[dict]) -> str:
        """
        Compresses the provided message history into a synthesis.
        
        Args:
            history: List of messages (role, content)
            
        Returns:
            String of the compressed synthesis.
        """
        if not history:
            return ""

        # Forming text for compression
        dialogue_text = ""
        for msg in history:
            dialogue_text += f"[{msg['role'].upper()}]: {msg['content']}\n"
        
        messages = [
            {"role": "system", "content": self.sublation_prompt},
            {"role": "user", "content": dialogue_text}
        ]
        
        try:
            import json
            raw_response = await self.llm.generate(messages)
            data = json.loads(raw_response)
            return data.get("response", "Failed to extract synthesis.")
        except Exception as e:
            print(f"[SublationEngine] Error compressing history: {e}")
            return "Summary of the previous conversation is unavailable due to an error."
