from dialectic_ai.core.llm import BaseLLM
from dialectic_ai.core.schema import ModelResult
from dialectic_ai.engine.parser import parse_llm_response, ParseError
from dialectic_ai.core.dialectical import dialectical

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
        prompt = f"""The previous response was intended to follow the required JSON schema,
but it could not be parsed.

Parsing error:
{original_error}

Invalid response:
{raw_response}

Repair the response so that it conforms exactly to the required JSON schema.

Rules:
- preserve the original semantic intent;
- do not add new reasoning or facts;
- do not remove information unless required for schema validity;
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
            return parsed, repaired
        except ParseError as repair_error:
            raise ControlledRepairError(
                "Failed to repair JSON response.",
                original_error=original_error,
                repair_error=repair_error,
                raw_response=raw_response
            ) from repair_error
