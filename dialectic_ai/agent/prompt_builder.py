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
from typing import Optional

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
   **An incomplete, empty, filtered, or erroring tool result is a reason to develop further, not to
   conclude.** A tool call that used the wrong name, a truncated list, or a search that came back with
   zero matches are all signals that your OWN attempt so far was incomplete -- not proof the underlying
   fact is false or the task can't be done. Before reporting "nothing matches," "the tool isn't
   available," or asking the user to resolve it, try at least one genuinely different concrete step: a
   different (actually available) tool, a corrected tool name, a narrower or wider filter, an
   offset/limit/pagination argument if a result was marked truncated. Only conclude something doesn't
   exist, or ask the user, after an alternative path has actually been tried and also failed -- not after
   a single attempt.
   **Never invent a value for a parameter you don't actually have** -- this applies to optional
   parameters exactly as much as to facts a tool could check. If the request or prior Observations don't
   give you a real value for an optional argument, omit that argument entirely rather than passing a
   plausible-looking placeholder, an empty container (`{}`, `[]`), or a guess. A tool call with fewer
   arguments (only the ones you actually know) is correct; a tool call with a made-up value for an
   argument you don't know is not "being thorough," it is fabricating input the same way inventing a
   fact would be.
3. **Opposite process, Contradiction, Leap -- REQUIRED every time you set `response` (not optional, not only
   for hard cases):**
   - `opposite_process`: name a process that would resolve or dissolve the task WITHOUT needing your
     simplest process at all. This is not "a harder version of the same plan" -- doing nothing, asking the
     user instead of acting, or the user handling it themselves manually are all valid opposite processes.
     **If none of your available tools are actually relevant to the request, recognizing that plainly is
     itself a complete, low-effort, fully valid opposite_process/leap -- it is NOT a harder or less
     complete answer than attempting a call.** Do not call a tool that only superficially resembles what
     was asked (the wrong entity, the wrong kind of data, a guess at what might be related) just to have
     called something -- an honest "no available tool answers this" is strictly better than a plausible-
     looking but wrong or irrelevant tool call, and costs you nothing extra to state.
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

WORKED EXAMPLE 2 (a real observed failure, not hypothetical -- see development_log.md, 2026-09-15):
task includes "reply to my latest email from Warunee" and "save all properties in Oslo under 1000 sqft."
A first attempt to fetch "the latest email" calls a tool name that does not exist and errors. A property
search returns a result explicitly marked truncated, and every apartment visible in the untruncated part
happens to be >= 1000 sqft.
  WRONG (an actual observed failure): concludes, after these two single attempts, "none of the properties
  meet the criteria" and effectively gives up on the email too, asking the user to "review the available
  properties" -- despite `Emails__search_emails`/`Emails__list_emails` being available, untried tools, and
  despite the property list being marked truncated rather than exhaustive. The oracle's own ground truth
  had 3 matching properties and 1 expected reply -- the conclusion was not just cautious, it was wrong.
  RIGHT: when the email tool call errors with "not registered," try a different, actually-available tool
  for the same goal (`Emails__search_emails` or `Emails__list_emails`) before concluding the email can't be
  handled. When the property search result says it was truncated, request more of it (pagination/offset,
  or a narrower query) before concluding no property matches -- a truncation notice is a statement about
  what you've seen so far, not about what exists.

WORKED EXAMPLE 3 (a real observed failure, not hypothetical -- see development_log.md, 2026-09-15):
request = "What is the largest planet in the universe?" Available tools include one named
`space.star_info(star_name, information)` -- nothing about planets, nothing that could compare sizes.
  WRONG (an actual observed failure): calls `space.star_info(star_name="Jupiter", information="diameter")`
  anyway -- Jupiter is a planet, not a star, and looking up one object's diameter doesn't answer a
  question that requires comparing across many objects regardless. The tool was called because it was
  the closest-sounding thing available, not because it could actually resolve the request.
  RIGHT: recognize that no available tool is relevant to this request, say so directly as `response`, and
  set `opposite_process` to naming that absence plainly (e.g. "answer from what I already know, since no
  tool here can compare planet sizes") -- this is a complete, correctly-resolved turn, not an incomplete
  one. Reaching for the nearest superficially-related tool is the failure this rule exists to prevent.
"""

_DIALECTICAL_RULES_MD = _AGENT_DIALECTICAL_RULES

from typing import Literal, Optional

FORMAT_INSTRUCTION_DIALECTIC_JSON = """
## Response format (STRICTLY JSON)
You must respond with a JSON object containing the following structure. Do not use conversational text outside the JSON.

IMPORTANT LANGUAGE & SPACING RULE:
All string fields ("decision", "assumption", "plan_steps", "opposite_process", "contradiction", "leap", "response") MUST be written in natural human language WITH NORMAL SPACES between words (раздельными словами с пробелами, полными предложениями). Never concatenate or glue words together without spaces!

```json
{
  "decision": "<string: short rationale for the chosen action, written with spaces between words>",
  "hypothesis": {
    "assumption": "<string: current hypothesis, natural sentence with spaces>",
    "plan_steps": ["<string: step description with spaces>"]
  },
  "knowledge_updates": [
    {"concept": "<string>", "status": "<string: learned|struggling|unknown>"}
  ],
  "tool_calls": [
    {"name": "<string: exact tool name>", "args": {"<string: arg name>": "<any: arg value>"}}
  ],
  "claims": [
    {
      "text": "<string: claim statement with spaces>",
      "evidence_ids": ["<string: id of evidence>"],
      "requires_validation": <boolean>
    }
  ],
  "response": "<string: final answer to the user with spaces, only if tool_calls is empty>",
  "opposite_process": "<string: REQUIRED whenever 'response' is set -- written with spaces between words>",
  "contradiction": "<string: REQUIRED whenever 'response' is set -- natural sentence with spaces>",
  "leap": "<string: REQUIRED whenever 'response' is set -- written with spaces between words>",
  "leap_type": "<REQUIRED whenever 'response' is set -- EXACTLY one of: 'decompose_and_act' | 'ask_only' | 'fully_resolved'>"
}
```
"""

FORMAT_INSTRUCTION_NATIVE = """
## Response format (STRICTLY JSON)
You must respond with a JSON object containing the following structure. Do not use conversational text outside the JSON.
When tool execution is required, invoke the available tools natively via provider function calling; do NOT include a "tool_calls" key in the JSON object.

IMPORTANT LANGUAGE & SPACING RULE:
All string fields ("decision", "assumption", "plan_steps", "opposite_process", "contradiction", "leap", "response") MUST be written in natural human language WITH NORMAL SPACES between words (раздельными словами с пробелами, полными предложениями). Never concatenate or glue words together without spaces!

```json
{
  "decision": "<string: short rationale for the chosen action, written with spaces between words>",
  "hypothesis": {
    "assumption": "<string: current hypothesis, natural sentence with spaces>",
    "plan_steps": ["<string: step description with spaces>"]
  },
  "knowledge_updates": [
    {"concept": "<string>", "status": "<string: learned|struggling|unknown>"}
  ],
  "claims": [
    {
      "text": "<string: claim statement with spaces>",
      "evidence_ids": ["<string: id of evidence>"],
      "requires_validation": <boolean>
    }
  ],
  "response": "<string: final answer to the user with spaces>",
  "opposite_process": "<string: REQUIRED whenever 'response' is set -- written with spaces between words>",
  "contradiction": "<string: REQUIRED whenever 'response' is set -- natural sentence with spaces>",
  "leap": "<string: REQUIRED whenever 'response' is set -- written with spaces between words>",
  "leap_type": "<REQUIRED whenever 'response' is set -- EXACTLY one of: 'decompose_and_act' | 'ask_only' | 'fully_resolved'>"
}
```
"""

FORMAT_INSTRUCTION = FORMAT_INSTRUCTION_DIALECTIC_JSON


def build_system_prompt(
    goal: str,
    tools: Optional[list] = None,
    tool_calling_mode: Literal["dialectic_json", "native"] = "dialectic_json",
    native_tool_calling: Optional[bool] = None,
) -> str:
    """Assembles the system prompt from the goal, rules, memory, and tools.

    Modes:
    - 'dialectic_json' (default): System prompt includes the full textual tool_calls specification
      and describes available tools. The engine acts as the sole dispatcher.
    - 'native': System prompt excludes textual tool_calls to avoid conflicting with provider
      native function calling schemas passed via API.
    """
    if native_tool_calling is not None:
        tool_calling_mode = "native" if native_tool_calling else "dialectic_json"

    tools_to_use = tools if tools is not None else []

    if tool_calling_mode == "dialectic_json":
        format_instruction = FORMAT_INSTRUCTION_DIALECTIC_JSON
        tools_section = ""
        if tools_to_use:
            tools_lines = "\n".join(t.to_prompt_description() for t in tools_to_use)
            tools_section = (
                "\n## Available tools (Confrontation with reality)\n"
                "Each tool below is listed as `name`, a description, and an `Arguments` JSON Schema -- the "
                "schema describes the SHAPE and TYPE your `args` must have (e.g. `{\"type\": \"string\"}` "
                "means \"put a string value here\"), it is not itself a value to copy. When you call a tool, "
                "`args` must be the actual values for THIS request (e.g. `{\"image_url\": \"the-real-url\"}`), "
                "never a restatement of the schema (`{\"type\": \"object\", \"properties\": {...}}`) -- that is "
                "a malformed call, not a cautious or complete one.\n"
                f"{tools_lines}\n"
            )
    elif tool_calling_mode == "native":
        format_instruction = FORMAT_INSTRUCTION_NATIVE
        tools_section = ""
    else:
        raise ValueError(f"Unknown tool_calling_mode: '{tool_calling_mode}'. Must be 'dialectic_json' or 'native'.")

    return f"""# Your goal
{goal}

{_DIALECTICAL_RULES_MD}
{format_instruction}{tools_section}
"""
