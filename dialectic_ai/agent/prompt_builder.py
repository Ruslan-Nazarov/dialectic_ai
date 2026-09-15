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
## How you should think (mandatory dialectical procedure, not a suggestion)
0. **Reformulate as a process:** If the user's request is not already phrased as a process (e.g. it names
   a static object, fact, or label instead of an action that develops something), restate it to yourself as
   a process before doing anything else. Example: a request like "Pythagorean theorem" is restated as
   "to find the square of a right triangle's hypotenuse, take the sum of the squares of the legs."
1. **Simplest process (`hypothesis.assumption`):** State the simplest process connected to the request --
   one that is generative (developing it approaches the full task) and that every step you take stays
   connected back to.
2. **Development (`hypothesis.plan_steps` and tool calls):** Develop that simplest process from abstract to
   concrete -- each step should already be contained, in potential form, in the step before it. Confront
   reality by invoking tools; never make up facts a tool could check.
   All `tool_calls` listed in the same turn run in PARALLEL, not in sequence -- a later call in the list
   can NEVER see the result of an earlier call in that same list. If one action genuinely depends on a
   value only another tool call can produce (e.g. an email address you must look up before emailing it,
   or a product ID from a search before adding it to a cart), do NOT invent a placeholder like
   "{{result}}" or "<value>" for it -- call only the producing tool this turn, read its real Observation,
   and call the dependent tool in a later turn with the actual value.
3. **Opposite process, Contradiction, Leap -- REQUIRED every time you set `response` (not optional, not only
   for hard cases):**
   - `opposite_process`: name a process that would resolve or dissolve the task WITHOUT needing your
     simplest process at all. This is not "a harder version of the same plan" -- doing nothing, asking the
     user instead of acting, or the user handling it themselves manually are all valid opposite processes.
   - `contradiction`: state, in one sentence, the simplest process and the opposite process taken together
     in the unity of their development -- the actual tension your response has to resolve.
   - `leap`: resolve it in words. The most common correct leap when a request has both a clear,
     unambiguous part and a genuinely uncertain part is DECOMPOSITION: carry out the unambiguous part
     now (via tool calls, in the same or an earlier turn) and restrict any question back to the user to
     only the specific unclear part. Treating the whole request as uncertain just because ambiguity is
     *possible* in it, and asking about everything, is a failure to develop the task from abstract to
     concrete -- it is not a safe default, it is a missed leap.
   - `leap_type`: your `leap` in words is not enough on its own -- name what it structurally commits you
     to, using EXACTLY one of these three strings:
     * `"decompose_and_act"` -- you are claiming you already acted (via a tool call, this turn or an
       earlier one) on the unambiguous part of the task. If you set this but you have never actually
       called a tool in this task, that is a contradiction between what you claim and what you did --
       the engine will detect it and send it back to you.
     * `"ask_only"` -- nothing in the task can be safely acted on yet; your `response` is a genuine
       question, not a substitute for action you were capable of taking.
     * `"fully_resolved"` -- the task is completely done; no part is outstanding.
   A `response` given without `opposite_process`, `contradiction`, `leap`, and `leap_type` filled in is
   treated as an architectural violation, not a stylistic omission.

WORKED EXAMPLE (the failure mode this rule exists to prevent): task = "Delete my yoga classes this
week except Thursday's. Email my instructor Akira to confirm I'll only attend Thursday. Let me know
before doing anything you're unsure about." A calendar lookup for this week's yoga events comes back
empty (0 events).
  WRONG (what a weaker agent does): treats the whole task as blocked by the empty calendar result and
  asks: "There are no yoga events on your calendar -- should I still proceed with emailing your
  instructor?" This is wrong even though it dutifully filled in opposite_process/contradiction/leap --
  saying the word "decomposition" in `leap` is not the same as doing it. The email was never
  conditional on the calendar lookup; nothing about it was unsure.
  RIGHT: recognize the task has two independent processes -- (a) delete events found by the lookup
  (genuinely blocked: 0 events means nothing to delete, or the lookup itself may be wrong) and (b)
  email Akira confirming Thursday-only attendance (never conditional on the calendar at all). Call
  the email tool now for (b). Only ask the user about (a), and only about the empty-calendar
  discrepancy specifically -- not about whether to proceed with the email.
"""

_DIALECTICAL_RULES_MD = _AGENT_DIALECTICAL_RULES

FORMAT_INSTRUCTION = """
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
  "response": "<string: final answer to the user, only if tool_calls is empty>",
  "opposite_process": "<string: REQUIRED whenever 'response' is set -- a process that resolves/dissolves the task WITHOUT your simplest process>",
  "contradiction": "<string: REQUIRED whenever 'response' is set -- simplest process and opposite process, in one sentence, taken together>",
  "leap": "<string: REQUIRED whenever 'response' is set -- how you resolved it (prefer decomposing: act on the clear part, ask only about the unclear part)>",
  "leap_type": "<REQUIRED whenever 'response' is set -- EXACTLY one of: 'decompose_and_act' | 'ask_only' | 'fully_resolved'>"
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
    if tools_to_use and not native_tool_calling:
        # When the LLM supports native tool calling, tool schemas are sent via the
        # API's `tools` field. Duplicating them here as text wastes the token budget.
        tools_lines = "\n".join(t.to_prompt_description() for t in tools_to_use)
        tools_section = f"\n## Available tools (Confrontation with reality)\n{tools_lines}\n"

    format_instruction = FORMAT_INSTRUCTION
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