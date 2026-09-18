import json
import os
import urllib.request
import urllib.error
import time
from typing import Dict, Any, Optional, Protocol, List
from pydantic import BaseModel, Field, ValidationError, ConfigDict

from dialectic_ai.v1.mocks import LLMRole


class SemanticLLMProvider(Protocol):
    def generate(self, system_prompt: str, user_prompt: str, response_format: Optional[dict] = None) -> str:
        pass


class OpenAILLMProvider:
    """Minimal provider without native tools. Retries on transport failures."""
    
    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        self.api_key = api_key or os.getenv("V1_LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.base_url = (base_url or os.getenv("V1_LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.model = model or os.getenv("V1_LLM_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
        
        if not self.api_key:
            raise ValueError("V1_LLM_API_KEY or OPENAI_API_KEY environment variable is required")

    def generate(self, system_prompt: str, user_prompt: str, response_format: Optional[dict] = None) -> str:
        url = f"{self.base_url}/chat/completions"
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if user_prompt:
            messages.append({"role": "user", "content": user_prompt})
            
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 1500,
        }
        if response_format:
            payload["response_format"] = response_format
            
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "DialecticAI-V1-RealLLM"
        }
        
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers)
        
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    return resp_data["choices"][0]["message"]["content"]
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8")
                if attempt == max_attempts - 1:
                    raise RuntimeError(f"LLM Provider Transport Error: {e.code} {e.reason} - {body}")
                print(f"Retry on HTTP {e.code}: {body}")
                time.sleep(1)
            except (urllib.error.URLError, TimeoutError) as e:
                if attempt == max_attempts - 1:
                    raise RuntimeError(f"LLM Provider Network Error: {e}")
                time.sleep(1)
        
        return ""


class GigaChatSemanticProvider:
    """Wraps the existing GigaChatLLM integration to match SemanticLLMProvider contract."""
    
    def __init__(self, auth_key: str = None, model: str = None):
        from dialectic_ai.integrations.gigachat.llm import GigaChatLLM
        self.auth_key = auth_key or os.getenv("GIGACHAT_AUTH_KEY")
        self.model = model or os.getenv("V1_LLM_MODEL") or "GigaChat"
        
        if not self.auth_key:
            raise ValueError("GIGACHAT_AUTH_KEY environment variable is required")
            
        self.llm = GigaChatLLM(auth_key=self.auth_key, model=self.model, max_retries=3)

    def generate(self, system_prompt: str, user_prompt: str, response_format: Optional[dict] = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if user_prompt:
            messages.append({"role": "user", "content": user_prompt})
            
        # GigaChatLLM handles its own transport retries and OAuth
        # response_format is handled by prompt engineering since _do_attempt doesn't pass it yet
        return self.llm._call_sync(messages)


# ==========================================
# Typed Parsers (Pydantic Models)
# ==========================================

class NormalizerOutput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    definition: str
    goal_state: str
    domain: str = "general"
    normalization_rationale: str = ""
    # Mapped to Mock expectations: description, goal_state
    
    def to_mock_format(self):
        return {
            "description": self.definition,
            "goal_state": self.goal_state
        }


class SimplestProposerOutput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    type_canonical_name: str
    description: str
    relation_to_target: str
    why_minimal: str
    generative_potential: str

    def to_mock_format(self):
        return {
            "type_canonical_name": self.type_canonical_name,
            "description": self.description
        }


class ProcessCandidate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    type_canonical_name: str
    description: str

class DevelopmentProposerOutput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    candidate_process: ProcessCandidate
    emergence_rationale: str
    potential_rationale: str
    determinacy_rationale: str

    def to_mock_format(self):
        return {
            "type_canonical_name": self.candidate_process.type_canonical_name,
            "description": self.candidate_process.description,
            "emergence_rationale": self.emergence_rationale,
            "potential_rationale": self.potential_rationale,
            "determinacy_rationale": self.determinacy_rationale
        }


class JudgeOutput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: str = Field(..., pattern="^(PASS|FAIL)$")
    reason: str


class OppositeProposerOutput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    candidate_process_id: str
    exclusion_rationale: str


class OppositeJudgeOutput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: str = Field(..., pattern="^(PASS|FAIL)$")
    reason: str
    
    def to_mock_format(self):
        return {
            "status": self.status,
            "exclusion_claim": self.reason
        }


class SufficiencyJudgeOutput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: str = Field(..., pattern="^(PASS|FAIL|NOT_APPLICABLE)$")
    reason: str


class DecomposedDevelopmentOutput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    distinctness_pass: bool
    immanence_pass: bool
    emergence_pass: bool
    retroactive_determinacy_pass: bool
    target_continuity_pass: bool
    workflow_only: bool
    reasoning: str


class DecomposedOppositeOutput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    excludes_need_for_simplest: bool
    alternative_only: bool
    reasoning: str


class DecomposedSufficiencyOutput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    goal_realizability: bool
    resolution_dependency: bool
    existing_path_sufficiency: bool
    reasoning: str


class TernaryDecision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    decision: str = Field(..., pattern="^(PASS|FAIL|UNCERTAIN|YES|NO)$")
    reason: str

class TernaryDevelopmentOutput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    distinctness_pass: TernaryDecision
    immanence_pass: TernaryDecision
    emergence_pass: TernaryDecision
    retroactive_determinacy_pass: TernaryDecision
    target_continuity_pass: TernaryDecision
    workflow_only: TernaryDecision

class TernaryOppositeOutput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    excludes_need_for_simplest: TernaryDecision
    alternative_only: TernaryDecision


# ==========================================
# Real LLM Dispatcher
# ==========================================

class RealLLMDispatcher:
    def __init__(self, provider: SemanticLLMProvider):
        self.provider = provider
        self.max_retries = 2

    def call(self, role: LLMRole, input_data: Dict[str, Any]) -> Dict[str, Any]:
        if role == LLMRole.PROCESS_NORMALIZER:
            return self._handle_normalizer(input_data)
        elif role == LLMRole.SIMPLEST_PROPOSER:
            return self._handle_simplest(input_data)
        elif role == LLMRole.DEVELOPMENT_PROPOSER:
            return self._handle_development(input_data)
        elif role == LLMRole.TRANSITION_JUDGE:
            return self._handle_development_judge(input_data)
        elif role == LLMRole.OPPOSITE_JUDGE:
            return self._handle_opposite_judge(input_data)
        elif role == LLMRole.SUFFICIENCY_JUDGE:
            return self._handle_sufficiency_judge(input_data)
        elif role == LLMRole.DEVELOPMENT_FACETS_JUDGE:
            return self._handle_development_facets_judge(input_data)
        elif role == LLMRole.OPPOSITE_FACETS_JUDGE:
            return self._handle_opposite_facets_judge(input_data)
        elif role == LLMRole.SUFFICIENCY_FACETS_JUDGE:
            return self._handle_sufficiency_facets_judge(input_data)
        elif role == LLMRole.TERNARY_DEVELOPMENT_FACETS_JUDGE:
            return self._handle_ternary_development_facets_judge(input_data)
        elif role == LLMRole.TERNARY_OPPOSITE_FACETS_JUDGE:
            return self._handle_ternary_opposite_facets_judge(input_data)
        raise ValueError(f"Unknown role {role}")

    def _call_and_parse(self, system_prompt: str, user_prompt: str, schema_cls: type[BaseModel]) -> BaseModel:
        # Use json_object response format
        response_format = {"type": "json_object"}
        system_prompt += "\n\nYou must return a valid JSON object matching the requested schema. Do NOT wrap it in markdown block quotes. Respond ONLY with JSON."
        
        last_error = None
        for attempt in range(self.max_retries):
            raw_response = self.provider.generate(system_prompt, user_prompt, response_format=response_format)
            
            # Clean possible markdown wrap
            raw_response = raw_response.strip()
            if raw_response.startswith("```json"):
                raw_response = raw_response[7:]
            elif raw_response.startswith("```"):
                raw_response = raw_response[3:]
            if raw_response.endswith("```"):
                raw_response = raw_response[:-3]
            raw_response = raw_response.strip()

            try:
                parsed_json = json.loads(raw_response)
                # Ensure we check for missing/extra fields stringently
                validated = schema_cls.model_validate(parsed_json, strict=True)
                return validated
            except json.JSONDecodeError as e:
                last_error = e
                user_prompt += f"\n\nPrevious response failed parsing as JSON. Error: {e}\nReturn a complete JSON object matching the required schema."
            except ValidationError as e:
                last_error = e
                error_msgs = []
                for err in e.errors():
                    loc = ".".join(map(str, err.get("loc", [])))
                    msg = err.get("msg", "")
                    error_msgs.append(f"- {loc}: {msg}")
                error_summary = "\n".join(error_msgs)
                user_prompt += f"\n\nPrevious response failed schema validation. Missing/invalid fields:\n{error_summary}\nReturn a complete JSON object matching the required schema."
                
        raise RuntimeError(f"Parser failure after {self.max_retries} attempts. Last error: {last_error}")

    def _handle_normalizer(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        system_prompt = (
            "You are the PROCESS_NORMALIZER. Your task is to normalize a raw user request into a formal TargetProcess.\n"
            "Return JSON with: definition (str), goal_state (str), domain (str), normalization_rationale (str)."
        )
        user_prompt = f"User Request: {input_data.get('text', '')}"
        res = self._call_and_parse(system_prompt, user_prompt, NormalizerOutput)
        return res.to_mock_format()

    def _handle_simplest(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        system_prompt = (
            "You are the SIMPLEST_PROPOSER. Given a TargetProcess, propose the most primitive, minimal process that begins to address the goal.\n"
            "Return JSON with: type_canonical_name (str), description (str), relation_to_target (str), why_minimal (str), generative_potential (str)."
        )
        user_prompt = f"Target Process: {input_data.get('target', '')}"
        res = self._call_and_parse(system_prompt, user_prompt, SimplestProposerOutput)
        return res.to_mock_format()

    def _handle_development(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        system_prompt = (
            "You are the DEVELOPMENT_PROPOSER. Given a source process, propose its next logical development transition.\n"
            "A development is an internal unfolding of the process, making what is implicit explicit.\n\n"
            "You MUST strictly follow this JSON format:\n"
            "{\n"
            '  "candidate_process": {\n'
            '    "type_canonical_name": "...",\n'
            '    "description": "..."\n'
            "  },\n"
            '  "emergence_rationale": "...",\n'
            '  "potential_rationale": "...",\n'
            '  "determinacy_rationale": "..."\n'
            "}\n\n"
            "CRITICAL: determinacy_rationale must explain how the emergence of the candidate process makes the SOURCE process more determinate. "
            "Do NOT include any additional authoritative fields such as status, validated, contradiction, leap, completed."
        )
        user_prompt = f"Source Process: {input_data.get('source', '')}\nProvide the next developmental step."
        res = self._call_and_parse(system_prompt, user_prompt, DevelopmentProposerOutput)
        return res.to_mock_format()

    def _handle_development_judge(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        system_prompt = (
            "You are the DEVELOPMENT_JUDGE. Evaluate if the proposed transition represents true development.\n"
            "Criteria:\n"
            "1. B arises from A.\n"
            "2. A potentially contains the possibility of B.\n"
            "3. The emergence of B makes A more determinate.\n"
            "A simple sequence of workflow steps (A happens before B, or B uses A) is NOT true development.\n"
            "Return JSON with: status ('PASS' or 'FAIL'), reason (str)."
        )
        user_prompt = (
            f"Source Process: {input_data.get('source')}\n"
            f"Candidate Process: {input_data.get('candidate')}\n"
            f"Emergence Rationale: {input_data.get('emergence_rationale')}\n"
            f"Potential Rationale: {input_data.get('potential_rationale')}\n"
            f"Determinacy Rationale: {input_data.get('determinacy_rationale')}\n"
        )
        res = self._call_and_parse(system_prompt, user_prompt, JudgeOutput)
        return {"status": res.status, "reason": res.reason}

    def _handle_opposite_judge(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        system_prompt = (
            "You are the OPPOSITE_JUDGE. Evaluate if P2 is the true Opposite of P0.\n"
            "Criteria:\n"
            "P2 must exclude the necessity of P0 to continue development. "
            "Important: alternative, replacement, or different implementations are NOT Opposites unless they exclude the necessity of the simplest process through development.\n"
            "Return JSON with: status ('PASS' or 'FAIL'), reason (str)."
        )
        user_prompt = (
            f"P0 (Simplest Process): {input_data.get('p0')}\n"
            f"P2 (Candidate Opposite): {input_data.get('p2')}\n"
            f"Exclusion Rationale: {input_data.get('exclusion_rationale', '')}\n"
            f"Development Path: {input_data.get('development_path', 'N/A')}\n"
        )
        res = self._call_and_parse(system_prompt, user_prompt, OppositeJudgeOutput)
        return res.to_mock_format()

    def _handle_sufficiency_judge(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        system_prompt = (
            "You are the SUFFICIENCY_JUDGE. Evaluate if the dialectical process has reached semantic sufficiency.\n"
            "Question: Can TargetProcess be achieved using the discovered processes WITHOUT resolving the validated contradiction?\n"
            "If NO (resolution is required because the contradiction blocks the target), return FAIL.\n"
            "If YES (the contradiction exists but doesn't block execution), return PASS.\n"
            "Return JSON with: status ('PASS', 'FAIL', or 'NOT_APPLICABLE'), reason (str)."
        )
        user_prompt = (
            f"Target Process: {input_data.get('target')}\n"
            f"Contradiction: {input_data.get('contradiction')}\n"
            "Evaluate if the TargetProcess can be achieved without resolving this contradiction."
        )
        res = self._call_and_parse(system_prompt, user_prompt, SufficiencyJudgeOutput)
        return {"status": res.status, "reason": res.reason}

    def _handle_development_facets_judge(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        system_prompt = (
            "You are the DEVELOPMENT_FACETS_JUDGE. Evaluate the proposed transition A -> B on multiple independent dimensions.\n\n"
            "Evaluate each facet:\n"
            "1. distinctness_pass (bool): Does B introduce a determination that is NOT yet actual in A in the same form, while still being allowed to arise from A?\n"
            "2. immanence_pass (bool): Before B becomes actual, is there a determination, tendency, criterion, structure, or potential within A that provides the internal ground from which B can arise?\n"
            "3. emergence_pass (bool): Does B arise through the unfolding/development of determinations present in A, rather than merely occurring after A or consuming A's output?\n"
            "4. retroactive_determinacy_pass (bool): Once B has emerged, does B make A more intelligible or determinate by revealing what implicit determination in A was developing toward B?\n"
            "5. target_continuity_pass (bool): Are A and B successive determinations of the SAME TargetProcess, even if they differ in method, form, abstraction level, or mode of realization?\n"
            "6. workflow_only (bool): Can the relation A->B be fully explained by an externally imposed sequence, dependency, instruction, or goal WITHOUT invoking any internal developmental relation between A and B? If yes, true.\n"
            "Return JSON matching the schema."
        )
        user_prompt = (
            f"Target Process: {input_data.get('target_process', 'N/A')}\n"
            f"Source Process A: {input_data.get('source')}\n"
            f"Candidate Process B: {input_data.get('candidate')}\n"
            f"Emergence Rationale: {input_data.get('emergence_rationale')}\n"
            f"Potential Rationale: {input_data.get('potential_rationale')}\n"
            f"Determinacy Rationale: {input_data.get('determinacy_rationale')}\n"
        )
        res = self._call_and_parse(system_prompt, user_prompt, DecomposedDevelopmentOutput)
        return res.model_dump()

    def _handle_opposite_facets_judge(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        system_prompt = (
            "You are the OPPOSITE_FACETS_JUDGE. Evaluate the proposed Opposite B of the simplest process A.\n\n"
            "Evaluate:\n"
            "1. excludes_need_for_simplest (bool): Can B continue its development/existence without requiring A as a necessary process?\n"
            "2. alternative_only (bool): Is B merely an alternative tool, substitution, or different technical implementation of A? If yes, true.\n"
            "Return JSON matching the schema."
        )
        user_prompt = (
            f"Simplest Process A: {input_data.get('p0')}\n"
            f"Candidate Opposite B: {input_data.get('p2')}\n"
            f"Exclusion Rationale: {input_data.get('exclusion_rationale', '')}\n"
            f"Development Path: {input_data.get('development_path', 'N/A')}\n"
        )
        res = self._call_and_parse(system_prompt, user_prompt, DecomposedOppositeOutput)
        return res.model_dump()

    def _handle_sufficiency_facets_judge(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        system_prompt = (
            "You are the SUFFICIENCY_FACETS_JUDGE. Evaluate if the TargetProcess is achievable given the current contradiction.\n\n"
            "Evaluate:\n"
            "1. goal_realizability (bool): Can TargetProcess be performed using already validated processes?\n"
            "2. resolution_dependency (bool): Does TargetProcess require resolving the relation between the contradiction sides to succeed?\n"
            "3. existing_path_sufficiency (bool): Does a validated path exist that achieves TargetProcess without resolution?\n"
            "Return JSON matching the schema."
        )
        user_prompt = (
            f"Target Process: {input_data.get('target')}\n"
            f"Contradiction: {input_data.get('contradiction')}\n"
        )
        res = self._call_and_parse(system_prompt, user_prompt, DecomposedSufficiencyOutput)
        return res.model_dump()

    def _handle_ternary_development_facets_judge(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        system_prompt = (
            "You are the TERNARY_DEVELOPMENT_FACETS_JUDGE. Evaluate the proposed transition A -> B on multiple independent dimensions.\n\n"
            "Evaluate each facet returning an object with {decision, reason}.\n"
            "For standard facets, decision MUST BE one of: 'PASS', 'FAIL', 'UNCERTAIN'.\n"
            "For workflow_only, decision MUST BE one of: 'YES', 'NO', 'UNCERTAIN'.\n"
            "Use UNCERTAIN ONLY when there is genuine semantic ambiguity, not as a shortcut.\n\n"
            "1. distinctness_pass: Does B introduce a determination that is NOT yet actual in A in the same form, while still being allowed to arise from A?\n"
            "2. immanence_pass: Before B becomes actual, is there a determination, tendency, criterion, structure, or potential within A that provides the internal ground from which B can arise?\n"
            "3. emergence_pass: Does B arise through the unfolding/development of determinations present in A, rather than merely occurring after A or consuming A's output?\n"
            "4. retroactive_determinacy_pass: Once B has emerged, does B make A more intelligible or determinate by revealing what implicit determination in A was developing toward B?\n"
            "5. target_continuity_pass: Are A and B successive determinations of the SAME TargetProcess, even if they differ in method, form, abstraction level, or mode of realization?\n"
            "6. workflow_only: Can the relation A->B be fully explained by an externally imposed sequence, dependency, instruction, or goal WITHOUT invoking any internal developmental relation between A and B?\n"
            "Return JSON matching the schema."
        )
        user_prompt = (
            f"Target Process: {input_data.get('target_process', 'N/A')}\n"
            f"Source Process A: {input_data.get('source')}\n"
            f"Candidate Process B: {input_data.get('candidate')}\n"
            f"Emergence Rationale: {input_data.get('emergence_rationale')}\n"
            f"Potential Rationale: {input_data.get('potential_rationale')}\n"
            f"Determinacy Rationale: {input_data.get('determinacy_rationale')}\n"
        )
        res = self._call_and_parse(system_prompt, user_prompt, TernaryDevelopmentOutput)
        return res.model_dump()

    def _handle_ternary_opposite_facets_judge(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        system_prompt = (
            "You are the TERNARY_OPPOSITE_FACETS_JUDGE. Evaluate the proposed Opposite B of the simplest process A.\n\n"
            "Evaluate each facet returning an object with {decision, reason}.\n"
            "For excludes_need_for_simplest, decision MUST BE one of: 'PASS', 'FAIL', 'UNCERTAIN'.\n"
            "For alternative_only, decision MUST BE one of: 'YES', 'NO', 'UNCERTAIN'.\n"
            "Use UNCERTAIN ONLY when there is genuine semantic ambiguity, not as a shortcut.\n\n"
            "1. excludes_need_for_simplest: Can B continue its development/existence without requiring A as a necessary process?\n"
            "2. alternative_only: Is B merely an alternative tool, substitution, or different technical implementation of A?\n"
            "Return JSON matching the schema."
        )
        user_prompt = (
            f"Simplest Process A: {input_data.get('p0')}\n"
            f"Candidate Opposite B: {input_data.get('p2')}\n"
            f"Exclusion Rationale: {input_data.get('exclusion_rationale', '')}\n"
            f"Development Path: {input_data.get('development_path', 'N/A')}\n"
        )
        res = self._call_and_parse(system_prompt, user_prompt, TernaryOppositeOutput)
        return res.model_dump()
