from dialectic_ai.agent.prompt_builder import FORMAT_INSTRUCTION
from dialectic_ai.core.dialectical import dialectical
from dialectic_ai.core.llm import BaseLLM
from dialectic_ai.core.schema import ModelResult
from dialectic_ai.engine.parser import ParseError, parse_llm_response


class ControlledRepairError(Exception):
    def __init__(self, message: str, original_error: ParseError, repair_error: Exception, raw_response: str):
        super().__init__(message)
        self.original_error = original_error
        self.repair_error = repair_error
        self.raw_response = raw_response


@dialectical(
    origin="LLM textual fallback can generate malformed JSON that breaks the dialectical engine",
    contradiction="If the engine crashes on invalid JSON, the agent fails abruptly. If it loops to repair, it wastes tokens and might get stuck.",
    resolves="A strict ONE-time controlled repair mechanism without endless loops, preserving semantic intent.",
    generates="Resilience against trivial schema errors, separate explicit error type (ControlledRepairError) if it truly fails.",
    own_contradictions="Costs extra tokens for the repair prompt. Doesn't guarantee fixing deep logic errors, only schema.",
    layer=3,
)
class JsonRepairer:
    """Handles controlled, one-time repair of malformed JSON responses from the LLM."""

    def __init__(self, llm: BaseLLM):
        self.llm = llm

    async def repair(self, raw_response: str, original_error: ParseError) -> tuple[dict, ModelResult]:
        """
        Attempts to repair a malformed JSON response.
        Returns a tuple of (parsed_dict, repaired_model_result) on success.
        Raises ControlledRepairError on failure.
        """
        # A response that was already long and malformed is re-embedded here verbatim
        # by default -- compounding whatever length/budget pressure likely caused the
        # original failure. Mirror the same cap used for tool observations in
        # engine/executor.py's _phase_collide (see development_log.md, 2026-09-15).
        max_raw_chars = 6000
        display_raw = raw_response
        if len(raw_response) > max_raw_chars:
            display_raw = (
                raw_response[:max_raw_chars]
                + f"\n... (truncated, {len(raw_response) - max_raw_chars} more characters omitted "
                  f"from this repair prompt -- the parsing error above should still identify what "
                  f"needs fixing.)"
            )
        prompt = f"""The previous response was intended to follow the required JSON schema below,
but it could not be parsed.
{FORMAT_INSTRUCTION}
Parsing error:
{original_error}

Invalid response:
{display_raw}

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
"""
        messages = [{"role": "user", "content": prompt}]
        
        # Call LLM without tools to enforce JSON only
        repaired = await self.llm.generate_result(messages)

        if repaired.tool_calls:
            raise ControlledRepairError(
                "Repair request resulted in a tool call instead of JSON text.",
                original_error=original_error,
                repair_error=ValueError("Unexpected tool calls"),
                raw_response=raw_response
            )

        try:
            parsed = parse_llm_response(repaired.text or "")
        except ParseError as repair_error:
            raise ControlledRepairError(
                "Failed to repair JSON response.",
                original_error=original_error,
                repair_error=repair_error,
                raw_response=raw_response
            ) from repair_error

        # A repair that parses as valid JSON but populates none of the schema's real fields
        # (decision/hypothesis/tool_calls/response) is not a success -- it means the repair
        # call reinvented its own field names instead of the ones requested. Silently
        # returning it produces an "empty turn" the engine cannot act on and previously
        # caused a real ~30-iteration stall (see development_log.md, 2026-09-13).
        has_content = bool(
            parsed.get("decision") or parsed.get("tool_calls") or
            parsed.get("response") or parsed.get("hypothesis")
        )
        if not has_content:
            raise ControlledRepairError(
                "Repair produced valid but schema-empty JSON (no decision/tool_calls/response/"
                "hypothesis) -- the repair call likely invented its own field names instead of "
                "reusing the requested schema.",
                original_error=original_error,
                repair_error=ValueError(f"Schema-empty repair result: {parsed}"),
                raw_response=raw_response
            )

        return parsed, repaired
