"""
dialectic_ai/engine/parser.py

DIALECTICAL DESCRIPTION:
  Origin: LLM returns a string. The engine needs structured data
    (thought, tool_calls, response). Without a parser — it's a mess.
  Contradiction: LLM violates JSON format — adds markdown wrappers, skips
    fields, generates invalid JSON. This is the most common failure point for the agent.
  How it solves: A reliable parser with multiple strategies for extracting JSON.
    Returns a structured dictionary or raises a clear exception.
  What it leads to: DialecticalEngine receives clean data. All parsing errors
    are handled in one place, not spreading throughout the code.
  Its own contradictions: The "smarter" the parser (regex, heuristics), the more
    edge cases it hides instead of forcing the LLM to follow the format.
    A soft parser reduces the model's discipline.
"""
import json
import re
from typing import Any, Optional
from pydantic import BaseModel, Field

class ParseError(Exception):
    """Parsing error of the LLM response."""
    pass


try:
    import json_repair
    JSON_REPAIR_AVAILABLE = True
except ImportError:
    JSON_REPAIR_AVAILABLE = False


class ClaimInput(BaseModel):
    text: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    requires_validation: bool = False

class HypothesisInput(BaseModel):
    assumption: str = ""
    plan_steps: list[str] = Field(default_factory=list)

class ParsedLLMResponse(BaseModel):
    hypothesis: Optional[HypothesisInput] = None
    decision: str = ""
    knowledge_updates: list[dict] = Field(default_factory=list)
    tool_calls: list[dict] = Field(default_factory=list)
    claims: list[ClaimInput] = Field(default_factory=list)
    response: str = ""
    
    def to_dict(self) -> dict:
        return self.model_dump(exclude_unset=True)


def parse_llm_response(raw: str) -> dict:
    """
    Parses the raw LLM response into a structured dictionary.

    Extraction strategies (in order of priority):
    1. Direct JSON parsing
    2. Extraction from markdown block ```json ... ```
    3. Finding the first { ... } in the string
    4. Optionally: json_repair to fix broken quotes/commas

    Returns:
        dict with fields: thought, knowledge_updates, tool_calls, response, claims, etc.

    Raises:
        ParseError: if no strategy worked
    """
    raw = raw.strip()

    def _try_parse(text: str) -> dict | None:
        try:
            data = json.loads(text)
            return ParsedLLMResponse(**data).to_dict()
        except Exception:
            if JSON_REPAIR_AVAILABLE:
                try:
                    repaired = json_repair.loads(text)
                    if isinstance(repaired, dict):
                        return ParsedLLMResponse(**repaired).to_dict()
                except Exception:
                    pass
        return None

    # Strategy 1: direct parsing
    parsed = _try_parse(raw)
    if parsed is not None: return parsed

    # Strategy 2: extract from ```json ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
    if match:
        parsed = _try_parse(match.group(1))
        if parsed is not None: return parsed

    # Strategy 3: find the first valid JSON object
    match = re.search(r"\{[\s\S]+\}", raw)
    if match:
        parsed = _try_parse(match.group(0))
        if parsed is not None: return parsed

    raise ParseError(f"Failed to parse LLM response:\n{raw[:300]}")
