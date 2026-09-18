from typing import Dict, Any
from enum import Enum, auto
from dialectic_ai.v1.models import (
    TargetProcess, ProcessInstance, ProcessType, DevelopmentTransition,
    OppositeRelation, SubCheckResult
)
from dialectic_ai.v1.state import (
    GraphPosition, NodeStatus, TransitionStatus, OppositeStatus, CheckStatus
)

class LLMRole(Enum):
    PROCESS_NORMALIZER = auto()
    SIMPLEST_PROPOSER = auto()
    DEVELOPMENT_PROPOSER = auto()
    TRANSITION_JUDGE = auto()
    OPPOSITE_JUDGE = auto()
    SUFFICIENCY_JUDGE = auto()
    DEVELOPMENT_FACETS_JUDGE = auto()
    OPPOSITE_FACETS_JUDGE = auto()
    SUFFICIENCY_FACETS_JUDGE = auto()
    TERNARY_DEVELOPMENT_FACETS_JUDGE = auto()
    TERNARY_OPPOSITE_FACETS_JUDGE = auto()

class MockLLMDispatcher:
    def __init__(self):
        self.call_count_dev_proposer = 0

    def call(self, role: LLMRole, input_data: Dict[str, Any]) -> Dict[str, Any]:
        if role == LLMRole.PROCESS_NORMALIZER:
            return {
                "description": "The process of determining whether a new item belongs to category X.",
                "goal_state": "Classification label assigned."
            }
        
        elif role == LLMRole.SIMPLEST_PROPOSER:
            return {
                "type_canonical_name": "Fresh human judgment",
                "description": "The process of individually classifying each item through a fresh human judgment."
            }
        
        elif role == LLMRole.DEVELOPMENT_PROPOSER:
            self.call_count_dev_proposer += 1
            if self.call_count_dev_proposer == 1:
                return {
                    "type_canonical_name": "Rule formulation",
                    "description": "The process of extracting and explicitly formulating a general classification rule from repeated individual classifications.",
                    "emergence_rationale": "Repeated individual classifications reveal a recurring criterion used across cases. Explicit rule formulation arises from making this recurring basis of judgment explicit.",
                    "potential_rationale": "Every individual classification already contains some basis on which the item was included or excluded. Repetition makes this implicit common basis available for abstraction.",
                    "determinacy_rationale": "P0 becomes more determinate as particular applications of an implicit general criterion rather than unrelated isolated judgments."
                }
            elif self.call_count_dev_proposer == 2:
                return {
                    "type_canonical_name": "Automatic formal application",
                    "description": "The process of automatically applying the formalized rule to new items without requiring a fresh individual human classification.",
                    "emergence_rationale": "Once the general rule has been made explicit and operational, it can be applied reproducibly to new inputs.",
                    "potential_rationale": "A formal classification rule contains the possibility of repeated application independently of the original individual judgments from which it was abstracted.",
                    "determinacy_rationale": "P1 becomes more determinate as an explicit executable classification procedure rather than merely a verbal generalization."
                }
            else:
                return {"stop": True} # For iteration stop
        
        elif role == LLMRole.TRANSITION_JUDGE:
            # Deterministic pass
            return {"status": "PASS"}

        elif role == LLMRole.OPPOSITE_JUDGE:
            # P2 excludes need for P0
            return {
                "status": "PASS",
                "exclusion_claim": "For new cases governed by the formalized rule, P2 can continue classifying items without requiring a fresh P0 individual judgment."
            }
        
        elif role == LLMRole.SUFFICIENCY_JUDGE:
            return {
                "status": "PASS",
                "reason": "The formal rule covers the required classification goal state."
            }

        elif role == LLMRole.DEVELOPMENT_FACETS_JUDGE:
            # Deterministic pass for all facets
            return {
                "distinctness_pass": True,
                "immanence_pass": True,
                "emergence_pass": True,
                "retroactive_determinacy_pass": True,
                "target_continuity_pass": True,
                "workflow_only": False,
                "reasoning": "Standard valid development mock."
            }
        
        elif role == LLMRole.OPPOSITE_FACETS_JUDGE:
            return {
                "excludes_need_for_simplest": True,
                "alternative_only": False,
                "reasoning": "Standard valid opposite mock."
            }

        elif role == LLMRole.SUFFICIENCY_FACETS_JUDGE:
            return {
                "goal_realizability": True,
                "resolution_dependency": False,
                "existing_path_sufficiency": True,
                "reasoning": "Standard sufficiency mock."
            }

        elif role == LLMRole.TERNARY_DEVELOPMENT_FACETS_JUDGE:
            return {
                "distinctness_pass": {"decision": "PASS", "reason": ""},
                "immanence_pass": {"decision": "PASS", "reason": ""},
                "emergence_pass": {"decision": "PASS", "reason": ""},
                "retroactive_determinacy_pass": {"decision": "PASS", "reason": ""},
                "target_continuity_pass": {"decision": "PASS", "reason": ""},
                "workflow_only": {"decision": "NO", "reason": ""}
            }
        
        elif role == LLMRole.TERNARY_OPPOSITE_FACETS_JUDGE:
            return {
                "excludes_need_for_simplest": {"decision": "PASS", "reason": ""},
                "alternative_only": {"decision": "NO", "reason": ""}
            }
        
        raise ValueError(f"Unknown role {role}")


def mock_rule_classifier(input_data: Dict[str, Any]) -> Dict[str, Any]:
    # Mock capability execution
    return {"classified": True, "category": "X", "confidence": 1.0}
