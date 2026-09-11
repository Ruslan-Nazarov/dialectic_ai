"""
dialectic_ai/engine/validator.py

DIALECTICAL DESCRIPTION:
  Origin: In Stage 3, the agent began issuing Claims with references to Evidence.
    But who checks that the agent did not make up the evidence_id or distort the facts?
  Contradiction: The agent generates conclusions itself, and it can also hallucinate.
    Without external validation, the framework allows lies to pass through.
  How it resolves: A separate component that checks:
    1. Do the claimed evidence_ids exist?
    2. Is the text of the Claim confirmed by the text of the Evidence (Fact-Checking through LLM)?
    Alternatives (RAG validation and Rule-based hallucination check) were
    rejected as either redundant (RAG requires a database) or too
    primitive (Rule-based). The LLM-as-a-judge model was chosen.
  What it leads to: The engine can reject the agent's final answer and force it
    to correct the mistake (Phase 4: VALIDATE).
  Own contradictions: Validation through LLM adds latency and cost
    (another model call). The LLM validator can also make mistakes (LLM-as-a-judge
    is not perfect, but better than no validation).
"""
import json
from dialectic_ai.core.schema import Claim, Evidence
from dialectic_ai.core.llm import BaseLLM
from dialectic_ai.core.dialectical import dialectical


@dialectical(
    origin="The agent may refer to a non-existent evidence_id or distort the fact (hallucination)",
    contradiction="The content generator cannot reliably check itself. External validation is needed",
    resolves="Introduces a separate LLM validator. (RAG and Rule-based rejected as redundant/primitive)",
    generates="Foundation for Phase 4: VALIDATE. The engine rejects false claims",
    own_contradictions="LLM-as-a-judge can also make mistakes. Increases latency (additional call)",
    layer=4,
)
class ClaimValidator:
    """
    Claim Validator (Fact-Checker).
    """
    def __init__(self, llm: BaseLLM, max_calls_per_session: int = 50):
        self.llm = llm
        self.max_calls_per_session = max_calls_per_session
        self._calls_per_session: dict[str, int] = {}

    async def validate(self, claim: Claim, evidence_list: list[Evidence], session_id: str = "default") -> str | None:
        """
        Checks the claim.
        Returns None if everything is fine, otherwise — a string with the error description.
        """
        if not claim.evidence_ids:
            if claim.requires_validation:
                return "The claim requires validation but does not refer to any evidence_id."
            return None  # Does not require validation

        # 1. Check for ID existence
        known_ids = {e.id: e for e in evidence_list}
        for eid in claim.evidence_ids:
            if eid not in known_ids:
                return f"The claim refers to an unknown evidence_id: '{eid}'."

        # 2. Fact-Checking (if needed)
        if not claim.requires_validation:
            return None

        # Check call limit
        current_calls = self._calls_per_session.get(session_id, 0)
        if current_calls >= self.max_calls_per_session:
            return f"Validation skipped: maximum number of validation calls ({self.max_calls_per_session}) exceeded for this session to prevent runaway billing."
        self._calls_per_session[session_id] = current_calls + 1

        # Collecting evidence texts
        evidence_texts = []
        for eid in claim.evidence_ids:
            evidence_texts.append(f"EVIDENCE {eid}:\n{known_ids[eid].content}")
        
        context = "\n\n".join(evidence_texts)

        prompt = f"""You are a strict fact-checker.
You are given facts (Evidence) and a claim (Claim).
Determine whether the Claim is supported by the Facts.

FACTS:
{context}

CLAIM:
{claim.text}

RESPOND STRICTLY IN JSON FORMAT:
{{
    "is_supported": true/false,
    "reason": "A brief explanation of why yes or why no."
}}
"""
        messages = [{"role": "system", "content": prompt}]
        try:
            raw_response = await self.llm.generate(messages)
            
            # Extracting JSON
            import re
            match = re.search(r"\{[\s\S]+\}", raw_response)
            if match:
                result = json.loads(match.group(0))
                # Validate the structure loosely
                is_supported = result.get("is_supported", False)
                reason = result.get("reason", "")
                
                if not is_supported:
                    return f"Not supported by the facts: {reason}"
                return None
            else:
                return "Internal validator error (not JSON)."
        except json.JSONDecodeError:
            return "Internal validator error (JSON Decode Error)."
        except Exception as e:
            return f"Error during validation: {str(e)}"
