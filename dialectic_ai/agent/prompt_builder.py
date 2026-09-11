"""
dialectic_ai/agent/prompt_builder.py

DIALECTICAL DESCRIPTION:
  Origin: The agent only sets the `goal`. But the LLM needs a complete
    system prompt with output rules, JSON format, memory context.
  Contradiction: If a developer writes the prompt manually, the dialectical rules
    of the framework do not get included in the prompt. The prompt and the philosophy of the framework diverge.
  How it resolves: Automatically assembles the system prompt from three parts:
    1) Dialectical rules (framework constant)
    2) The specific agent's goal (set by the developer)
    3) The current state of memory (derived from Memory)
  What it leads to: The engine (engine.py) receives the ready prompt through a single call.
    The agent always "remembers" its dialectical duties.
  Own contradictions: The prompt grows along with the memory. With a large knowledge graph,
    it may exceed the model's context window. A compression strategy is needed.
"""
from pathlib import Path
from dialectic_ai.memory.base import BaseMemory


_AGENT_DIALECTICAL_RULES = """
## How you should think (Dialectical cycle)
1. **Thesis (Hypothesis):** Formulate an assumption or plan based on your goal and memory.
2. **Antithesis (Confrontation with reality):** Test the hypothesis by invoking available tools. Never make up facts.
3. **Synthesis:** Having obtained data from the tools, resolve the contradiction and provide a final answer or a new hypothesis.
"""

_DIALECTICAL_RULES_MD = _AGENT_DIALECTICAL_RULES

# Instruction for JSON format — separate from the rules
_FORMAT_INSTRUCTION = """
## Response format (STRICTLY JSON)
```json
{
  "hypothesis": {
    "assumption": "Current hypothesis (e.g., 'The problem is with indentation' or 'Need to verify fact X')",
    "plan_steps": ["Step 1", "Step 2"]
  },
  "thought": "Internal monologue: analysis, decision to invoke a tool",
  "knowledge_updates": [{"concept": "...", "status": "learned|struggling|unknown|introduced"}],
  "tool_calls": [{"name": "tool_name", "args": {"key": "value strictly according to the tool's JSON Schema"}}],
  "claims": [
    {
      "text": "Separate logical statement.",
      "evidence_ids": ["uuid_from_observation_if_any"],
      "requires_validation": false
    }
  ],
  "response": "Concatenation of all claims into a single readable text for the user (ONLY if tool_calls is empty)"
}
```
"""



def build_system_prompt(goal: str, memory: BaseMemory, tools: list = None) -> str:
    """Assembles the system prompt from the goal, rules, memory, and tools."""
    
    rules = []
    
    # Base rules
    rules.append("1. STRUCTURE: You must always respond strictly in JSON format. Do not add markdown like ```json, just the pure object.")
    
    tools_to_use = tools if tools is not None else []

    tools_section = ""
    if tools_to_use:
        tools_lines = "\n".join(t.to_prompt_description() for t in tools_to_use)
        tools_section = f"\n## Available tools (Confrontation with reality)\n{tools_lines}\n"

    memory_context = memory.get_context()

    return f"""# Your goal
{goal}

{_DIALECTICAL_RULES_MD}
{_FORMAT_INSTRUCTION}{tools_section}
## Current state of memory
{memory_context}
"""