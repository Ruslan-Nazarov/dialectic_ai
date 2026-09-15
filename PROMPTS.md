# DialecticAI — Every Prompt in the System, Verbatim

**Date:** 2026-09-15
**Purpose:** A single reference for every place in the codebase that constructs text sent to an LLM. Useful for (a) hackathon pitch prep — this is the actual "brain" of the framework, (b) prompt engineering work without re-deriving each prompt's location from scratch, (c) handing off prompt-tuning work to a different AI session. Every block below is copied verbatim from the source file as of this date; if you edit a prompt, update this file in the same commit/session or it will drift.

For *why* each prompt looks the way it does (the incidents and live experiments that shaped the wording), see `development_log.md`'s 2026-09-13/14/15 entries and `HANDOFF.md`.

---

## 1. The core agent system prompt — `dialectic_ai/agent/prompt_builder.py`

This is assembled by `build_system_prompt(goal, memory, tools, native_tool_calling)` for **every single agent** in the framework, with no exceptions — every example, every CLI-created agent, every GAIA2 benchmark run, every Triad/Debate role. It is the one prompt that matters most if you want to change how *any* agent built on this framework reasons.

Assembly order: `# Your goal\n{goal}\n\n{RULES}\n{FORMAT}\n{tools_section}\n## Current state of memory\n{memory_context}`

### 1a. `_AGENT_DIALECTICAL_RULES` (the "how you should think" block)

```
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
```

**Provenance:** Step 0 and the parallel-execution paragraph in step 2 were added 2026-09-14/15, cheap and universal, never independently A/B tested (see `CODE_REVIEW.md`). Step 1 is original. Step 3 (opposite_process/contradiction/leap/leap_type) and the worked example were added 2026-09-13/14 in direct response to a live-reproduced failure (see `HANDOFF.md` — the "Yoga scenario" incident) and the worked example specifically **was** measured before/after: 0/3 correct email sends before, 3/3 after, on the exact same reproduction script.

### 1b. `FORMAT_INSTRUCTION` (the JSON contract)

```
## Response format (STRICTLY JSON)
You must respond with a JSON object containing the following structure. Do not use conversational text outside the JSON.

​```json
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
​```
```

**Important implementation detail:** when `native_tool_calling=True` (the LLM provider supports native function/tool calling, e.g. `OpenAILLM`, `GigaChatLLM` does NOT), the `"tool_calls": [...]` block is stripped out of this template via **line-based string matching** before it's sent — see `CODE_REVIEW.md` → Layer 1 for why this is fragile if you edit the JSON template's formatting.

### 1c. Tools section (conditionally included)
Only included when `native_tool_calling=False` (tools are described as text instead of via the API's native `tools` parameter):
```
## Available tools (Confrontation with reality)
{one line per tool, from Tool.to_prompt_description(): "- `{name}`: {description}\n  Arguments: {json schema}"}
```

### 1d. Memory section (always included)
```
## Current state of memory
{memory.get_context()}
```
The exact text here depends on which `Memory` implementation is wired in — see `CODE_REVIEW.md` → Layer 1 for the caveat that `PersistentMemory`/`TraceReader.get_knowledge_graph()` only fully work with the default `KnowledgeGraphMemory`.

---

## 2. JSON repair prompt — `dialectic_ai/engine/repair.py` (`JsonRepairer.repair`)

Fired whenever `parse_llm_response()` fails on the main agent turn. Runs as a **separate LLM call with no tools and no system prompt** (just this one user message) — deliberately isolated so the repair call can't itself trigger a tool call or inherit unrelated context.

```
The previous response was intended to follow the required JSON schema below,
but it could not be parsed.
{FORMAT_INSTRUCTION -- the full block from section 1b above, embedded verbatim}
Parsing error:
{original_error}

Invalid response:
{raw_response}

Repair the response so that it conforms EXACTLY to the JSON schema shown above -- reusing its
exact field names ("decision", "hypothesis", "tool_calls", "claims", "response", etc.), not
field names of your own invention. If the invalid response already contains a final answer for
the user, that answer belongs in the "response" field, not in some other key.

Rules:
- preserve the original semantic intent;
- do not add new reasoning or facts;
- do not remove information unless required for schema validity;
- use the field names from the schema above, exactly;
- return JSON only;
- do not use Markdown fences;
- do not call tools.
```

**Provenance / do not regress this:** before 2026-09-13, this prompt said "conforms exactly to the required JSON schema" **without ever stating what that schema was** — the repair call would invent its own field names (`contacts`, `criteria`, `result` instead of `decision`, `response`, ...), silently produce a schema-empty object, and cause a ~30-iteration/~30-minute stall. The embedded `{FORMAT_INSTRUCTION}` and the explicit "use the field names from the schema above" instruction are the fix. **Known remaining gap:** `{raw_response}` is embedded with no length cap — see `REFACTOR_PLAN.md` Phase 1.4.

---

## 3. Agent-creation goal refinement — `dialectic_ai/cli/architect.py` (`DialecticalArchitect.design`)

Runs **once, at agent-creation time** (inside the `dialectic create` wizard, opt-in via a plain-language yes/no question), not at agent runtime. Its only output that matters downstream is `refined_goal`, which becomes the created agent's `goal` (fed into prompt block 1 above, like any other agent's goal).

```
You are designing the identity of a new AI agent, before any code is written for it.

The developer gave you this in plain language:
- Agent name: {name}
- Goal, as the developer wrote it: {raw_goal}
- Tools available to the agent: {tools}

Work through these five steps and report them, but the developer will never see your reasoning —
only the final refined goal matters to them:

1. Simplest process: the simplest process connected to this agent's purpose — one that is
   generative (the agent's whole behavior can be approached by developing it) and that
   everything the agent does should stay connected back to.
2. Development: develop that simplest process from abstract to concrete into a short chain of
   concrete responsibilities this agent must actually carry out (using the tools it has).
3. Opposite process: a process that would make this agent's simplest process unnecessary — for
   example, a way the task gets handled (well or badly) WITHOUT this agent's core process ever
   running (e.g. the user doing it manually, or the agent silently guessing instead of checking).
   This is not "a competing tool," it is a process that does not need the simplest process to exist.
4. Contradiction: state the simplest process and the opposite process together, in the unity of
   their development, as one sentence naming the real tension the agent's design must resolve.
5. Leap: resolve the contradiction with a concrete behavioral rule or emphasis that a system prompt
   can actually enforce - it must explicitly close off the opposite process's failure mode while
   fully carrying out the simplest process's development.

Then write `refined_goal`: a rewritten, concrete version of the developer's goal (2-4 sentences,
still first-person "You are..." style suitable for a system prompt) that bakes in the leap - it
should read as an ordinary, well-written agent goal, with no mention of "thesis," "dialectics,"
"contradiction," or any philosophical vocabulary.

Respond with STRICT JSON only, no markdown fences, matching exactly:
{
  "simplest_process": "...",
  "development_chain": ["...", "..."],
  "opposite_process": "...",
  "contradiction": "...",
  "leap": "...",
  "refined_goal": "..."
}
```

**Live-verified example output** (from a real run this session, goal = "You help users save shopping notes."):
- simplest_process: *"Collect and store shopping notes from user input."*
- opposite_process: *"User manually records shopping items in a separate medium, eliminating the need for the agent to collect and store notes."*
- leap: *"I will always ask the user if they want to store notes with me; if they decline, I will offer to export the notes to a file they can keep elsewhere, ensuring the notes are still captured but not stored by me."*
- refined_goal (what actually shipped into the generated agent): *"You are NoteBot, an assistant that helps users save shopping notes. You ask for shopping items, organize them into a structured list, and store them for easy retrieval. If a user prefers not to keep notes with you, you offer to export the notes so they can keep them elsewhere. You always confirm the user's preference before storing."*

---

## 4. Multi-agent debate prompts — `dialectic_ai/multi/debate.py` (`DialecticalDebateEngine.run_debate`)

Three separate `DialecticalAgent`/`DialecticalEngine` instances, each still gets the *full* core prompt from section 1 (goal + rules + format) — these are **additional** user-message content layered on top, not replacements.

### 4a. Thesis prompt
```
Task: {user_topic}

Step 1 (Simplest process): Identify the simplest process connected to this task — one that
is generative (the full solution can be approached by developing it) and that every part of
your eventual solution will stay connected back to.
Step 2 (Development): Develop that simplest process from abstract to concrete — each step
of your plan should already be contained, in potential form, in the step before it. Use your
hypothesis.plan_steps for this chain.
Provide your concrete solution as the final response.
```

### 4b. Antithesis prompt
```
Task: {user_topic}

Do NOT critique any specific existing solution and do NOT propose a mere alternative
implementation/library/practice for the same need — that is a different, weaker move.
Instead, find and develop a process that solves or dissolves this task WITHOUT ever needing
the most obvious, simplest starting process most people would reach for. Your process's own
development must not require that simplest process to exist at all.
State in your decision field, in one sentence, which simplest process yours does not need,
then develop your own process from abstract to concrete and give your solution as the final response.
```

### 4c. Synthesis prompt
```
Task: {user_topic}

Simplest process (Thesis) and its concrete solution:
- Simplest process: {simplest_process}
- Solution: {thesis_output.response}

Opposite process (Antithesis) and its concrete solution:
- Opposite process: {opposite_process}
- Solution: {antithesis_output.response}

These two, taken together in the unity of their development, are your `contradiction`. Resolve
it with your `leap`: either a process that replaces both, absorbing what each was developing
toward into its own development, or a process that makes it possible for both to keep existing
side by side until a later process replaces them. State your final answer as `response`.
```

**Note:** the Synthesis role does **not** need any special instruction to produce `contradiction`/`leap`/`leap_type` — those come from the *core* prompt (section 1) that every agent already has. This is a deliberate simplification made 2026-09-14: an earlier version of this file asked Synthesis to prefix its answer with regex-parseable `LEAP: ...` / `CONTRADICTION: ...` lines; that convention was deleted once the core schema carried the same fields natively for every agent, not just this one.

---

## 5. Multi-agent triad prompts — `dialectic_ai/multi/triad.py` (`DialecticalTriad.run`)

Older, simpler sibling of Debate (predates the Rule 5 rigor added 2026-09-13). Only the Antithesis and Synthesis roles get extra prompt text; Thesis just receives the raw task as-is.

### 5a. Antithesis prompt
```
Original task: {task}

Your task is to independently propose a contrarian, critical, or alternative approach to this task.
Do not try to solve it in the standard way. Find edge cases, potential flaws in obvious solutions,
and propose a robust alternative.
```
**Note the difference from Debate's Antithesis prompt (4b):** this one explicitly asks for "a contrarian... alternative approach" — the weaker "alternative practice" framing that `debate.py`'s own docstring and prompt (4b) were written specifically to move past ("do NOT propose a mere alternative implementation/library/practice"). Triad has not been updated to match Debate's stricter framing. If you want Triad to have the same rigor as Debate, port prompt 4b's wording here — this has not been done as of this document (see `REFACTOR_PLAN.md` for whether that's worth doing versus leaving Triad as the intentionally-lighter-weight sibling).

### 5b. Synthesis prompt
```
Original task: {task}

Proposed solution (Thesis):
{draft}

Critique of this solution (Antithesis):
{critique}

Your task is to resolve the conflict. Take the best from the Thesis, correct the mistakes,
pointed out by the Antithesis, and provide the ideal, final result.
```

---

## 6. Claim validation ("fact-checker") prompt — `dialectic_ai/engine/validator.py` (`ClaimValidator.validate`)

Fired only when a `Claim.requires_validation` is `True` and its `evidence_ids` all resolve to real evidence. Rate-limited to `max_calls_per_session` (default 50) per session to bound cost.

```
You are a strict fact-checker.
You are given facts (Evidence) and a claim (Claim).
Determine whether the Claim is supported by the Facts.

FACTS:
{evidence_texts, one "EVIDENCE {id}:\n{content}" block per referenced evidence_id}

CLAIM:
{claim.text}

RESPOND STRICTLY IN JSON FORMAT:
{
    "is_supported": true/false,
    "reason": "A brief explanation of why yes or why no."
}
```

---

## 7. GAIA2 benchmark adapter's task-specific goal — `benchmarks/gaia2/adapter.py` (`DialecticAREAgent.run_scenario`)

This is **not** a separate LLM call — it's additional text prepended to the `goal` parameter passed into the ordinary `DialecticalAgent` constructor, so it becomes part of the `# Your goal` section at the very top of the core prompt (section 1), ahead of the framework's own rules.

```
You are an AI assistant that executes tasks strictly using the provided tools. Respond with a final answer when done.
[System] Current simulated date and time is: {env_time}
[!] Rule: Never claim a product, contact, or email was not found until you explicitly verify all fields in the tool Observation output. Do not hallucinate truncations.
[!] CRITICAL RULE: A single ambiguous sub-item must never block unrelated sub-items. If you need to ask the user a clarifying question (e.g. via AgentUserInterface__send_message_to_user), do NOT stop and do NOT generate a final response! You MUST immediately continue using tools to execute EVERY other unrelated planned action. Only provide a final response when ALL possible actions have been completed.
[!] Rule: If you are forced to stop or ask the user a question, you MUST summarize all partial progress you have already achieved.
```

**Important:** `{env_time}` was, for the entire duration of this project until 2026-09-14, **always wrong by exactly one year** (hardcoded fallback `"2023-10-04 12:00:00"` because the `hasattr(scenario, "environment")` check that was supposed to compute it correctly was checking an attribute that does not exist anywhere in the ARE API). See `HANDOFF.md` for the full incident. If you are debugging *any* date/calendar-related agent behavior on this benchmark, verify `env_time` is actually correct for the specific scenario first, before assuming the agent's reasoning is at fault.

**Overlap with the core prompt's own rules:** the "CRITICAL RULE" here (decompose, don't block on ambiguity) is conceptually the same instruction as section 1's step 3/worked-example, written independently, before the core prompt had its own version. They are not contradictory, but they are two different people's wording of the same idea living in two different files — worth consolidating (see `REFACTOR_PLAN.md`) so a future prompt-quality fix doesn't have to be made in two places to actually take effect end-to-end for GAIA2 runs.

---

## 8. Framework/agent methodology audit prompt — `dialectic_ai/observability/audit_prompt.md`

Loaded as a template by `DialecticalAuditor._load_prompt_template()`, with `{METHODOLOGY_PRODUCT}`, `{METHODOLOGY_PROCESS}`, `{AUDIT_MODE}`, `{CONTEXT}` substituted before sending. This is a **file**, not inline Python — edit `dialectic_ai/observability/audit_prompt.md` directly to change it; do not look for this text in any `.py` file. See that file directly for the current full text (it is long — a role statement, two analysis sections with a required summary-table format, and an explicit "do not evaluate code style/performance/beauty, only the 4 [now 5] rules" scope limiter). `{METHODOLOGY_PROCESS}` is generated by `DialecticalAuditor._get_process_methodology()` in `dialectic_ai/observability/auditor.py` — this is the one place Rule 5 (added 2026-09-13/14) is spelled out for the audit LLM; see that method directly for its current full text, which is too long to usefully duplicate here without drifting out of sync — treat `auditor.py` as the source of truth and this file as a pointer to it.

## 9. Contradiction root-cause investigation prompt — `dialectic_ai/observability/auditor.py` (`DialecticalAuditor.investigate_contradiction`)

Also long (embeds the full raw LLM response, full prompt, and relevant framework source files for one specific contradiction event) — see `auditor.py`'s `investigate_contradiction` method directly for the current exact text rather than duplicating it here. The structure is: role statement (root-cause investigator, not a fixer) → the specific event's forensic data → the relevant source files (`_CORE_CHAIN_FILES` plus a provider-specific file from `_PROVIDER_FILE_MAP`) → a three-part reporting format (hypothesis, responsible file/mechanism, one-off-vs-systemic judgment).

---

## Tools whose descriptions are fed into prompts (not prompts themselves, but LLM-visible text worth tracking here)

Every `Tool.to_prompt_description()` call (used when `native_tool_calling=False`) renders as:
```
- `{tool.name}`: {tool.description}
  Arguments: {json.dumps(tool.parameters())}
```
`AREToolWrapper.description` (in `benchmarks/gaia2/adapter.py`) additionally appends a return-type hint and, for any tool whose name contains `list_`, this extra line:
```
[!] Use this ONLY to list all items without filtering. For searching/filtering, use the corresponding search_* tool.
```
This is the *only* place in the codebase that proactively steers the model away from an expensive/bloated tool call toward a cheaper one — worth knowing about if you're trying to reduce token usage on other tool-heavy scenarios, since the same pattern could be generalized (see `REFACTOR_PLAN.md`).
