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

_FORMAT_INSTRUCTION = """
## Response format (STRICTLY JSON)
You must respond with a JSON object containing the following structure. Do not use conversational text outside the JSON.

```json
{
  "decision": "<string: short rationale for the chosen action>",
  "hypothesis": {
    "assumption": "<string: current hypothesis>",
    "plan_steps": ["<string: step description>"]
  },
  "knowledge_updates": [
    {"concept": "<string>", "status": "<string: learned|struggling|unknown>"}
  ],
  "tool_calls": [
    {"name": "<string: exact tool name>", "args": {"<string: arg name>": "<any: arg value>"}}
  ],
  "claims": [
    {
      "text": "<string: claim statement>",
      "evidence_ids": ["<string: id of evidence>"],
      "requires_validation": <boolean>
    }
  ],
  "response": "<string: final answer to the user, only if tool_calls is empty>"
}
```
"""




def build_system_prompt(goal: str, memory: BaseMemory, tools: list = None, native_tool_calling: bool = False) -> str:
    """Assembles the system prompt from the goal, rules, memory, and tools."""
    
    rules = []
    
    # Base rules
    rules.append("1. STRUCTURE: You must always respond strictly in JSON format. Do not add markdown like ```json, just the pure object.")
    
    tools_to_use = tools if tools is not None else []

    tools_section = ""
    if tools_to_use:
        tools_lines = "\n".join(t.to_prompt_description() for t in tools_to_use)
        tools_section = f"\n## Available tools (Confrontation with reality)\n{tools_lines}\n"

    format_instruction = _FORMAT_INSTRUCTION
    if native_tool_calling:
        # Remove tool_calls from textual JSON requirement
        # Simple string manipulation since it's a static format
        lines = format_instruction.splitlines()
        filtered_lines = []
        skip = False
        for line in lines:
            if '"tool_calls": [' in line:
                skip = True
            elif skip and '],' in line:
                skip = False
                continue
            elif not skip:
                filtered_lines.append(line)
        format_instruction = "\n".join(filtered_lines)

    memory_context = memory.get_context()

    return f"""# Your goal
{goal}

{_DIALECTICAL_RULES_MD}
{format_instruction}{tools_section}
## Current state of memory
{memory_context}
"""