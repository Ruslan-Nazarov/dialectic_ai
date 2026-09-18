from enum import Enum, auto

class RunState(Enum):
    INIT = auto()
    NORMALIZING_TARGET = auto()
    FINDING_SIMPLEST = auto()
    DEVELOPING = auto()
    CHECKING_OPPOSITE = auto()
    COMPUTING_BLOCKING_SET = auto()
    CHECKING_SUFFICIENCY = auto()
    EXECUTION_PLANNING = auto()
    EXECUTING = auto()
    COMPLETED = auto()
    INCOMPLETE = auto()
    FAILED = auto()

class DialecticalStatus(Enum):
    IN_PROGRESS = auto()
    SEMANTIC_STOP = auto()
    COMPUTATIONAL_STOP = auto()

class SemanticStopReason(Enum):
    CONTRADICTION_FOUND = auto()

class ComputationalStopReason(Enum):
    ITERATION_BUDGET_EXHAUSTED = auto()
    RELEVANCE_FRONTIER_EXHAUSTED = auto()

class RunOutcome(Enum):
    EXECUTION_COMPLETE = auto()
    SEMANTIC_INCOMPLETE = auto() # Aborted gracefully because dialectical process cannot proceed
    SEMANTIC_REJECTED = auto() # Candidate process rejected by judges
    SEMANTIC_UNRESOLVED = auto() # Ternary judge uncertainty prevented validation or rejection
    BLOCKING_CONTRADICTION = auto() # Validated contradiction prevents execution
    EXECUTION_FAILURE = auto() # Technical execution failed
    FRAMEWORK_FAILURE = auto()

class GraphPosition(Enum):
    ROOT = auto()
    INTERIOR = auto()
    OPPOSITE = auto()
    RESOLVING = auto()

class NodeStatus(Enum):
    PROPOSED = auto()
    VALIDATED = auto()
    REJECTED = auto()
    ACTIVE = auto()

class TransitionStatus(Enum):
    PROPOSED = auto()
    VALIDATED = auto()
    REJECTED = auto()

class OppositeStatus(Enum):
    CANDIDATE = auto()
    VALIDATED = auto()
    DISCARDED = auto()

class ContradictionStatus(Enum):
    CANDIDATE = auto()
    VALIDATED = auto()
    DISCARDED = auto()
    UNRESOLVED = auto()

class CheckStatus(Enum):
    PASS = auto()
    FAIL = auto()
    NOT_APPLICABLE = auto()

class EvidenceSourceType(Enum):
    RESEARCH_ACTION = auto()
    TOOL_CALL = auto()
    LLM_OUTPUT = auto()
    FRAMEWORK_DERIVATION = auto()

class EvidenceLinkType(Enum):
    SUPPORTS_CLAIM = auto()
    SUPPORTS_TRANSITION = auto()
    SUPPORTS_EXCLUSION = auto()
    SUPPORTS_EXECUTION = auto()

class ActionContextLoop(Enum):
    DISCOVERY = auto()
    EXECUTION = auto()

class ExecutionDependencyType(Enum):
    DEPENDS_ON = auto()
    PARALLEL_WITH = auto()
    FALLBACK_TO = auto()
    RETRY_WITH = auto()
