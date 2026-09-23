"""
dialectic_ai/cli/architect.py

DIALECTICAL DESCRIPTION:
  Origin: `creator.py`'s wizard lets a developer create an agent from a plain-language
    goal and a tool list alone — the developer need not know dialectics. But the raw
    goal was used verbatim: no actual Simplest -> Development -> Opposite -> Contradiction
    -> Leap work happened for that specific agent, only generic vocabulary was inherited.
  Contradiction: We want every framework-produced agent to be dialectically designed
    (Rule 1: Generative Beginning), but we also do not want to burden the developer with
    philosophy they may not know. Developer simplicity and framework-wide rigor pull in
    opposite directions if the developer is the one who has to perform the analysis.
  How it resolves: Moves the procedure OFF the developer and INTO the framework itself.
    DialecticalArchitect takes the developer's plain-language goal and tool descriptions
    and runs Simplest -> Development -> Opposite -> Contradiction -> Leap automatically,
    in one LLM call, producing a refined goal (the leap) plus a written record. The
    developer only ever answers ordinary questions and gets back an ordinary working agent.
  What it leads to: `creator.py` can now write, alongside the agent script/config, an
    audit-ready `<agent>_development_log.md` that DialecticalAuditor.audit_agent() already
    knows how to read — no new plumbing needed there.
  Own contradictions: Adds one extra LLM call (cost + latency) at creation time, not at
    runtime. Quality of the internal reasoning depends on the LLM and is invisible to the
    developer unless they read the generated log. If no LLM is reachable, the pass is
    skipped and the agent falls back to the developer's raw goal, verbatim.
"""
import json
import re

from pydantic import BaseModel, Field

from dialectic_ai.core.dialectical import DialecticalObject, dialectical
from dialectic_ai.core.llm import BaseLLM

try:
    import json_repair
    JSON_REPAIR_AVAILABLE = True
except ImportError:
    JSON_REPAIR_AVAILABLE = False


class ArchitectResult(BaseModel):
    simplest_process: str
    development_chain: list[str] = Field(default_factory=list)
    opposite_process: str
    contradiction: str
    leap: str
    refined_goal: str


class ArchitectError(Exception):
    """Raised when the design pass could not produce a usable result (caller should fall back)."""
    pass


_DESIGN_PROMPT = """You are designing the identity of a new AI agent, before any code is written for it.

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
{{
  "simplest_process": "...",
  "development_chain": ["...", "..."],
  "opposite_process": "...",
  "contradiction": "...",
  "leap": "...",
  "refined_goal": "..."
}}
"""


@dialectical(
    origin="creator.py's wizard let a developer create an agent from a plain-language goal and "
           "tool list alone, using the raw goal verbatim -- no dialectical work happened for that "
           "specific agent, only generic class-level vocabulary was inherited.",
    contradiction="Every framework-produced agent should be dialectically designed (Rule 1), but "
                  "the developer creating it should not need to know what dialectics is.",
    resolves="Runs the full Simplest -> Development -> Opposite -> Contradiction -> Leap procedure "
             "automatically, inside the framework, from the developer's plain-language inputs alone; "
             "the developer only answers ordinary questions and receives an ordinary working agent.",
    generates="An audit-ready <agent>_development_log.md per created agent, readable by the existing "
              "DialecticalAuditor.audit_agent() without any new plumbing.",
    own_contradictions="Adds one extra LLM call (cost, latency, and failure surface) at creation time. "
                       "The reasoning quality depends on the LLM and is invisible to the developer "
                       "unless they open the generated log. Falls back to the raw goal, verbatim, if "
                       "no LLM is reachable.",
    layer=6,
    simplest_process="A developer states an agent's goal in plain language, with no dialectical vocabulary.",
    opposite_process="Asking the developer to author the simplest/opposite-process/contradiction/leap "
                     "analysis themselves -- a process that needs no automated reasoning at all, only "
                     "developer literacy in dialectics.",
)
class DialecticalArchitect(DialecticalObject):
    """
    Runs the Rule 5 procedure on a developer's plain-language agent goal, automatically.

    Usage:
        architect = DialecticalArchitect(llm)
        result = await architect.design("WebResearcher", "Find facts on the web.", ["web_search"])
        print(result.refined_goal)
    """

    def __init__(self, llm: BaseLLM):
        self.llm = llm

    async def design(self, name: str, raw_goal: str, tool_descriptions: list[str]) -> ArchitectResult:
        tools_text = ", ".join(tool_descriptions) if tool_descriptions else "(no tools)"
        prompt = _DESIGN_PROMPT.format(name=name, raw_goal=raw_goal, tools=tools_text)
        messages = [{"role": "user", "content": prompt}]

        try:
            raw_response = await self.llm.generate(messages)
        except Exception as e:
            raise ArchitectError(f"LLM call failed: {e}") from e

        data = self._parse_json(raw_response)
        if data is None:
            raise ArchitectError(f"Could not parse design response as JSON:\n{str(raw_response)[:300]}")

        try:
            return ArchitectResult(**data)
        except Exception as e:
            raise ArchitectError(f"Design response did not match the expected schema: {e}") from e

    @staticmethod
    def _parse_json(raw: str) -> dict | None:
        raw = (raw or "").strip()

        def _try(text: str):
            try:
                return json.loads(text)
            except Exception:
                if JSON_REPAIR_AVAILABLE:
                    try:
                        repaired = json_repair.loads(text)
                        if isinstance(repaired, dict):
                            return repaired
                    except Exception:
                        pass
            return None

        parsed = _try(raw)
        if parsed is not None:
            return parsed

        match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
        if match:
            parsed = _try(match.group(1))
            if parsed is not None:
                return parsed

        match = re.search(r"\{[\s\S]+\}", raw)
        if match:
            return _try(match.group(0))

        return None

    @staticmethod
    def render_log_entry(agent_name: str, raw_goal: str, result: ArchitectResult) -> str:
        """Renders the Rule 5 write-up for this agent, in the same template used in development_log.md."""
        chain = "\n  ".join(f"{i + 1}. {step}" for i, step in enumerate(result.development_chain))
        return f"""# Dialectical Design Log: {agent_name}

*Auto-generated by `DialecticalArchitect` (dialectic_ai/cli/architect.py) from the developer's plain-language goal. Readable by `DialecticalAuditor.audit_agent(log_path=...)`.*

## Agent creation — Rule 5 worked pass

- **Developer's raw goal:** {raw_goal}
- **Simplest process:** {result.simplest_process}
- **Development (abstract -> concrete):**
  {chain}
- **Opposite process:** {result.opposite_process}
- **Contradiction:** {result.contradiction}
- **Leap:** {result.leap}
- **Refined goal (used in the generated agent):** {result.refined_goal}
"""

