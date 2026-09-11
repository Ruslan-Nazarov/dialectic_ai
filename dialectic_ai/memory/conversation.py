"""
dialectic_ai/memory/conversation.py

Simple memory that stores the history of the dialogue, without being tied to a knowledge graph.
"""
from dialectic_ai.memory.base import Memory
from dialectic_ai.core.schema import AgentInput


class ConversationMemory:
    """Stores the history of user requests and final responses from the agent."""

    def __init__(self, max_turns: int = 10):
        self.max_turns = max_turns
        self.history: list[dict] = []

    def process_turn(self, user_input: AgentInput, parsed_response: dict) -> None:
        """Add a turn to the history."""
        self.history.append({
            "role": "user",
            "content": user_input.user_message
        })
        
        response_text = parsed_response.get("response", "")
        if response_text:
            self.history.append({
                "role": "assistant",
                "content": response_text
            })
            
        # Trim old turns (each turn = 2 messages)
        if len(self.history) > self.max_turns * 2:
            self.history = self.history[-(self.max_turns * 2):]

    def get_context(self) -> str:
        """Return the history as text."""
        if not self.history:
            return "The dialogue history is empty."
            
        context_parts = ["--- DIALOGUE HISTORY ---"]
        for msg in self.history:
            role = "User" if msg["role"] == "user" else "Assistant"
            context_parts.append(f"{role}: {msg['content']}")
            
        return "\n".join(context_parts)

    def clear(self) -> None:
        """Clear the history."""
        self.history = []
