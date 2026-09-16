"""
benchmarks/ablation/bare_agent.py

DIALECTICAL DESCRIPTION:
  Origin: Neither GAIA2 (benchmarks/gaia2/) nor BFCL (benchmarks/bfcl/) actually isolates what
    THIS FRAMEWORK contributes. GAIA2 conflates framework quality with raw model planning
    capability (a free-tier model's multi-step reasoning ceiling dominates the result). BFCL
    tests a single LLM call in isolation, so it can never exercise anything that only matters
    across multiple turns -- which is exactly where this framework's real engineering happened
    this session (JSON repair on a malformed turn, the empty-turn nudge, the "don't give up
    after one failed attempt" prompt rule, the leap_action_mismatch second-order-contradiction
    loop-back).
  Contradiction: To isolate the framework's contribution, you need to hold the LLM and the task
    fixed and vary only the ORCHESTRATION LOGIC around it -- but "the orchestration logic" is
    normally inseparable from `DialecticalEngine` itself; there was no lesser version to compare
    against.
  How it resolves: A deliberately minimal "bare" agent loop -- same LLM provider (so HTTP-level
    retry/backoff is identical in both conditions; that's a network-reliability concern, not a
    dialectical one), same `Tool` interface, same multi-turn structure -- but with NONE of
    DialecticalEngine's own recovery logic: no `JsonRepairer` on a malformed response (a bad
    parse is just a failure), no empty-turn nudge, no leap/Rule-5 requirements in the prompt, no
    second-order contradiction detection. Comparing task completion between this and the real
    engine, on scenarios with a DELIBERATELY INJECTED failure (see scenarios.py), isolates
    exactly the mechanisms this session actually built.
  What it leads to: A cheap (no external benchmark dataset, no live simulation environment),
    fully controllable ablation harness -- new failure-injection scenarios can be added
    incrementally, each giving a standalone, reportable result before the next is attempted.
  Own contradictions: The bare loop's own prompt is a judgment call about what "no framework"
    means -- too weak a bare prompt would make the comparison unfair in the framework's favor,
    too strong (e.g. secretly encoding "retry on failure") would erase the very difference being
    measured. Keep it as close as possible to BFCL's own raw-prompt spirit (`benchmarks/bfcl/adapter.py`'s
    `run_raw_turn`): tool descriptions, a JSON output contract, no strategic guidance beyond that.
"""
import json
from dataclasses import dataclass, field

from dialectic_ai.core.llm import BaseLLM
from dialectic_ai.core.schema import AgentInput


def build_bare_system_prompt(goal: str, tools: list) -> str:
    """The 'no framework' system prompt: goal + tool schemas + a bare JSON contract. No
    dialectical rules, no worked examples, no recovery guidance -- deliberately the multi-turn
    analogue of BFCL's `run_raw_turn` baseline prompt."""
    tools_text = "\n".join(t.to_prompt_description() for t in tools)
    return f"""{goal}

Available tools:
{tools_text}

Respond with ONLY a JSON object, no other text:
{{"tool_calls": [{{"name": "<tool name>", "args": {{...}}}}], "response": "<final answer -- only when you are done, otherwise empty>"}}

Call tools when you need information or must take an action. Set "response" only once the task is complete.
"""


@dataclass
class BareRunResult:
    status: str                    # "completed" | "max_iterations" | "parse_error" | "format_error" | "empty_turn_stuck" | "error"
    response: str = ""
    iterations: int = 0
    tool_calls_made: list = field(default_factory=list)   # [{"name", "args", "success"}]
    error: str = ""


class BareAgentLoop:
    """Minimal ReAct-style loop: call the LLM, execute any `tool_calls` literally via each
    Tool's real `execute()` (so injected failures in scenarios.py are genuinely encountered),
    feed back raw results, repeat until a `response` or `max_iterations`. No repair, no nudge,
    no Rule 5. This is the 'bare'/'no framework' condition for the ablation comparison.
    """

    def __init__(self, llm: BaseLLM, goal: str, tools: list, max_iterations: int = 10):
        self.llm = llm
        self.tools = tools
        self._tool_registry = {t.name: t for t in tools}
        self.max_iterations = max_iterations
        self._system_prompt = build_bare_system_prompt(goal, tools)

    async def run(self, user_input: AgentInput) -> BareRunResult:
        messages = [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": user_input.user_message},
        ]
        tool_calls_made = []

        for iteration in range(1, self.max_iterations + 1):
            try:
                result = await self.llm.generate_result(messages)
            except Exception as e:
                return BareRunResult(status="error", iterations=iteration,
                                      tool_calls_made=tool_calls_made, error=str(e))

            raw_text = result.text or ""
            try:
                parsed = json.loads(raw_text)
            except json.JSONDecodeError:
                # The bare loop has no repair mechanism -- a malformed response is a hard stop.
                return BareRunResult(status="parse_error", response=raw_text, iterations=iteration,
                                      tool_calls_made=tool_calls_made)

            if not isinstance(parsed, dict):
                # Syntactically valid JSON (e.g. a bare string or number) that isn't the expected
                # object shape -- the bare loop has no schema validation either, so this is a
                # hard stop too, not a crash. (Caught live: a real GigaChat response nested
                # "response" as an object instead of a string -- see development_log.md.)
                return BareRunResult(status="format_error", response=raw_text, iterations=iteration,
                                      tool_calls_made=tool_calls_made)

            raw_tool_calls = parsed.get("tool_calls")
            tool_calls = raw_tool_calls if isinstance(raw_tool_calls, list) else []
            raw_response = parsed.get("response")
            response_text = raw_response.strip() if isinstance(raw_response, str) else ""

            if tool_calls:
                obs_parts = []
                for call in tool_calls:
                    if not isinstance(call, dict):
                        obs_parts.append(f"[Error] Malformed tool_calls entry (not an object): {call!r}")
                        continue
                    name = call.get("name")
                    args = call.get("args", {}) or {}
                    if not isinstance(args, dict):
                        obs_parts.append(f"[Error] Tool '{name}' called with non-object args: {args!r}")
                        tool_calls_made.append({"name": name, "args": args, "success": False})
                        continue
                    tool = self._tool_registry.get(name)
                    if not tool:
                        obs_parts.append(f"[Error] Tool '{name}' is not registered.")
                        tool_calls_made.append({"name": name, "args": args, "success": False})
                        continue
                    evidence = await tool.execute(args)
                    tool_calls_made.append({"name": name, "args": args, "success": evidence.success})
                    if evidence.success:
                        obs_parts.append(f"[{name}] Result: {evidence.content}")
                    else:
                        obs_parts.append(f"[{name}] Error: {evidence.error}")
                messages.append({"role": "assistant", "content": raw_text})
                messages.append({"role": "user", "content": "\n".join(obs_parts)})
                continue

            if response_text:
                return BareRunResult(status="completed", response=response_text, iterations=iteration,
                                      tool_calls_made=tool_calls_made)

            # Empty turn (no tool_calls, no response) -- the bare loop has no nudge mechanism.
            return BareRunResult(status="empty_turn_stuck", iterations=iteration,
                                  tool_calls_made=tool_calls_made)

        return BareRunResult(status="max_iterations", iterations=self.max_iterations,
                              tool_calls_made=tool_calls_made)
