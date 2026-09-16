"""
benchmarks/ablation/engineered_agent.py

DIALECTICAL DESCRIPTION:
  Origin: The first ablation result (flaky_retry, development_log.md 2026-09-15/16) showed the
    framework beating a bare loop 100% vs 35% -- but the actual mechanism (an empty-turn nudge,
    a duplicate-action check) is generic software engineering, not anything specifically
    dialectical. That result proves DialecticalEngine has good engineering; it does NOT prove
    the dialectical method itself (Rule 5: simplest/development/opposite/contradiction/leap)
    contributes anything beyond what the same engineering would give without it.
  Contradiction: To isolate "does dialectics specifically matter" from "does having any
    robustness engineering at all matter," a two-way comparison (bare vs full framework) cannot
    tell them apart -- both differences are bundled into one number.
  How it resolves: A third condition, EngineeredAgentLoop -- BareAgentLoop's structure plus the
    SAME generic robustness features DialecticalEngine has (an empty-turn nudge, duplicate-
    successful-action detection, one JSON-repair retry) but with NONE of the dialectical
    vocabulary: no Rule 5 prompt text, no opposite_process/contradiction/leap/leap_type fields,
    no worked examples about decomposition, no leap_action_mismatch second-order-contradiction
    check. Comparing engineered vs framework (holding the generic engineering constant) isolates
    the dialectical method's own marginal contribution; comparing bare vs engineered isolates
    generic engineering's contribution on its own.
  What it leads to: A genuine three-way ablation -- bare < engineered < framework would be real,
    specific evidence dialectics adds something past generic engineering; engineered ~= framework
    would mean the earlier flaky_retry win was engineering, not dialectics, and should be
    reported as such rather than credited to the method it was not actually testing.
  Own contradictions: "Generic engineering, no dialectics" is itself a judgment call about which
    features count as one or the other -- the nudge/dedup/repair triad was chosen because
    they're the exact three mechanisms that explained the flaky_retry result, not an exhaustive
    list of everything DialecticalEngine does.
"""
import json
from typing import Optional

from dialectic_ai.core.llm import BaseLLM

from benchmarks.ablation.bare_agent import BareRunResult, build_bare_system_prompt


async def _minimal_json_repair(llm: BaseLLM, raw_text: str) -> Optional[dict]:
    """One repair attempt using a MINIMAL schema (tool_calls/response only) -- no Rule 5
    vocabulary, unlike the real JsonRepairer (engine/repair.py), whose repair prompt embeds the
    full FORMAT_INSTRUCTION including opposite_process/contradiction/leap/leap_type. Using the
    real JsonRepairer here would leak dialectical requirements into the supposedly-non-dialectical
    condition."""
    prompt = (
        "The previous response could not be parsed. It must be a single JSON object of exactly "
        'this shape: {"tool_calls": [{"name": "<tool name>", "args": {...}}], "response": "<string>"}.\n\n'
        f"Invalid response:\n{raw_text}\n\n"
        'Return ONLY the corrected JSON object, reusing the field names "tool_calls" and "response" exactly.'
    )
    try:
        result = await llm.generate_result([{"role": "user", "content": prompt}])
        parsed = json.loads(result.text or "")
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


class EngineeredAgentLoop:
    """BareAgentLoop plus generic, non-dialectical robustness engineering: an empty-turn nudge
    (bounded to 2 consecutive empty turns, then a hard stop -- mirroring DialecticalEngine's own
    idle-loop bound), duplicate-successful-action detection (skip re-executing, tell the model it
    already has this result), and one minimal JSON-repair retry on a malformed response. This is
    the 'generic engineering, no dialectics' condition for the ablation comparison.
    """

    def __init__(self, llm: BaseLLM, goal: str, tools: list, max_iterations: int = 10):
        self.llm = llm
        self.tools = tools
        self._tool_registry = {t.name: t for t in tools}
        self.max_iterations = max_iterations
        self._system_prompt = build_bare_system_prompt(goal, tools)

    async def run(self, user_input) -> BareRunResult:
        messages = [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": user_input.user_message},
        ]
        tool_calls_made = []
        executed_actions: set = set()
        empty_turn_count = 0

        for iteration in range(1, self.max_iterations + 1):
            try:
                result = await self.llm.generate_result(messages)
            except Exception as e:
                return BareRunResult(status="error", iterations=iteration,
                                      tool_calls_made=tool_calls_made, error=str(e))

            raw_text = result.text or ""
            parsed = None
            try:
                candidate = json.loads(raw_text)
                if isinstance(candidate, dict):
                    parsed = candidate
            except json.JSONDecodeError:
                pass

            if parsed is None:
                parsed = await _minimal_json_repair(self.llm, raw_text)
                if parsed is None:
                    return BareRunResult(status="parse_error", response=raw_text, iterations=iteration,
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

                    action_key = (name, json.dumps(args, sort_keys=True))
                    if action_key in executed_actions:
                        obs_parts.append(f"[Note] '{name}' with these exact arguments was already "
                                          f"executed successfully. No need to repeat it.")
                        continue

                    tool = self._tool_registry.get(name)
                    if not tool:
                        obs_parts.append(f"[Error] Tool '{name}' is not registered.")
                        tool_calls_made.append({"name": name, "args": args, "success": False})
                        continue

                    evidence = await tool.execute(args)
                    tool_calls_made.append({"name": name, "args": args, "success": evidence.success})
                    if evidence.success:
                        executed_actions.add(action_key)
                        obs_parts.append(f"[{name}] Result: {evidence.content}")
                    else:
                        obs_parts.append(f"[{name}] Error: {evidence.error}")

                messages.append({"role": "assistant", "content": raw_text})
                messages.append({"role": "user", "content": "\n".join(obs_parts)})
                empty_turn_count = 0
                continue

            if response_text:
                return BareRunResult(status="completed", response=response_text, iterations=iteration,
                                      tool_calls_made=tool_calls_made)

            # Empty turn -- generic liveness nudge (not a dialectical mechanism), bounded so it
            # cannot loop forever, mirroring DialecticalEngine's own idle-loop bound in spirit.
            empty_turn_count += 1
            if empty_turn_count > 2:
                return BareRunResult(status="empty_turn_stuck", iterations=iteration,
                                      tool_calls_made=tool_calls_made)
            messages.append({"role": "assistant", "content": raw_text})
            messages.append({"role": "user", "content": "You did not call a tool or provide a response. "
                                                          "Please continue: call a tool, or give your final "
                                                          "response now if you are done."})

        return BareRunResult(status="max_iterations", iterations=self.max_iterations,
                              tool_calls_made=tool_calls_made)
