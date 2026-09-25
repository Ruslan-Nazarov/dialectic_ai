from typing import Any, Dict

from jsonschema import Draft202012Validator

MOVE_SPECIFICATIONS: Dict[str, Dict[str, Any]] = {
    "PROPOSE_SIMPLEST": {
        "description": "Start with the most abstract, simplest generative process connected to the goal.",
        "payload_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "The simplest generative process formulation"}
            },
            "required": ["content"]
        }
    },
    "ASSESS_SIMPLEST": {
        "description": "Assess if the candidate simplest process is generative and connected to the goal.",
        "payload_schema": {
            "type": "object",
            "properties": {
                "candidate_simplest_id": {"type": "string", "description": "ID of the Candidate Simplest designation"},
                "approved": {"type": "boolean", "description": "True if approved, False if rejected"}
            },
            "required": ["candidate_simplest_id", "approved"]
        }
    },
    "DEVELOP_PROCESS": {
        "description": "Unfold a committed process into a more concrete emergent process.",
        "payload_schema": {
            "type": "object",
            "properties": {
                "source_process_id": {"type": "string", "description": "ID of the source process"},
                "emergent_content": {"type": "string", "description": "Content of the new emergent process"},
                "potential_containment": {"type": "string", "description": "How the emergent was implicitly contained in the source"},
                "emergence": {"type": "string", "description": "The mechanism that made it emerge"},
                "concretization": {"type": "string", "description": "How it makes the source more concrete"},
                "new_content": {"type": "string", "description": "What is qualitatively new"}
            },
            "required": ["source_process_id", "emergent_content", "potential_containment", "emergence", "concretization", "new_content"]
        }
    },
    "CONNECT_DEVELOPMENT": {
        "description": "Establish a development relation between two existing processes.",
        "payload_schema": {
            "type": "object",
            "properties": {
                "source_process_id": {"type": "string", "description": "ID of the source process"},
                "emergent_process_id": {"type": "string", "description": "ID of the emergent process"},
                "potential_containment": {"type": "string", "description": "How the emergent was implicitly contained in the source"},
                "emergence": {"type": "string", "description": "The mechanism that made it emerge"},
                "concretization": {"type": "string", "description": "How it makes the source more concrete"},
                "new_content": {"type": "string", "description": "What is qualitatively new"}
            },
            "required": ["source_process_id", "emergent_process_id", "potential_containment", "emergence", "concretization", "new_content"]
        }
    },
    "PROPOSE_ACTION": {
        "description": "Call a domain tool to collide with reality.",
        "payload_schema": {
            "type": "object",
            "properties": {
                "tool_name": {"type": "string", "description": "Name of the tool to call"},
                "args": {"type": "object", "description": "Arguments for the tool"},
                "origin_ref": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "enum": ["Process", "DevelopmentRelation", "Contradiction", "PracticeAssessment"]},
                        "id": {"type": "string"}
                    },
                    "required": ["type", "id"],
                    "description": "Reference to the entity that demands this action"
                },
                "why_now": {"type": "string"},
                "purpose": {"type": "string"},
                "expectation": {"type": "string", "description": "What concrete result is expected from this action?"},
                "relation_to_goal": {"type": "string"}
            },
            "required": ["tool_name", "args", "origin_ref", "why_now", "purpose", "expectation", "relation_to_goal"]
        }
    },
    "ASSESS_PRACTICE": {
        "description": "Assess the Observation resulting from an Action.",
        "payload_schema": {
            "type": "object",
            "properties": {
                "action_id": {"type": "string", "description": "ID of the Action"},
                "observation_id": {"type": "string", "description": "ID of the Observation"},
                "expected_actual_relation": {"type": "string", "enum": ["confirmed", "partially_confirmed", "contradicted", "inconclusive"],
                    "description": (
                        "Compare the OBSERVATION's actual raw_result to what the Action's own `expectation` field "
                        "predicted -- NOT whether your explanation of what happened is itself correct. "
                        "'confirmed': raw_result matches the expectation. 'contradicted': raw_result does NOT "
                        "match the expectation (e.g. expectation said 391, raw_result says 400 -- this is "
                        "'contradicted', even though your explanation correctly identifies the mismatch). "
                        "'partially_confirmed': matches on some but not all of what was expected. "
                        "'inconclusive': the observation cannot settle it either way. Writing an accurate "
                        "explanation of a discrepancy while still marking 'confirmed' is a contradiction between "
                        "this field and your own explanation, and will be rejected."
                    )},
                "explanation": {"type": "string", "description": "Explanation of the relation"},
                "consequence_for_development": {"type": "string", "description": "How this affects further development"}
            },
            "required": ["action_id", "observation_id", "expected_actual_relation", "explanation", "consequence_for_development"]
        }
    },
    "DESIGNATE_OPPOSITE": {
        "description": "Designate the Opposite: a process found among the Simplest's developing processes whose own development does not require the Simplest.",
        "payload_schema": {
            "type": "object",
            "properties": {
                "simplest_id": {"type": "string", "description": "The designation record's OWN 'id' field, taken from the Designations list where role == 'simplest'. Do NOT use that record's process_id, and do NOT use a process id from the Processes list."},
                "context_id": {"type": "string", "description": "The 'id' of an existing, already-listed Process or Development Relation from the state above that the opposite develops out of. Never the goal_id, never a Designation id."},
                "content": {"type": "string", "description": "The opposite process (e.g. 'heating of food'), not an alternative solution or a negation"},
                "independence": {"type": "string", "description": "Why this process's own development does not require the simplest (e.g. 'food can be heated whether or not this food is cold')"},
                "justification": {"type": "string", "description": "Which developing process of the simplest this is and how it arose there"}
            },
            "required": ["simplest_id", "context_id", "content", "independence", "justification"]
        }
    },
    "ESTABLISH_CONTRADICTION": {
        "description": "Establish a contradiction between the Simplest and the Opposite.",
        "payload_schema": {
            "type": "object",
            "properties": {
                "simplest_id": {"type": "string", "description": "The designation record's OWN 'id' field, taken from the Designations list where role == 'simplest'. Do NOT use that record's process_id."},
                "opposite_id": {"type": "string", "description": "The designation record's OWN 'id' field, taken from the Designations list where role == 'opposite'. Do NOT use that record's process_id."},
                "simplest_dev_ref_ids": {"type": "array", "items": {"type": "string"}, "description": "IDs of development references for simplest"},
                "opposite_dev_ref_ids": {"type": "array", "items": {"type": "string"}, "description": "IDs of development references for opposite"},
                "unity_justification": {"type": "string", "description": "Why these opposites form a unity"},
                "developing_unity_description": {"type": "string", "description": "Description of their unity in development"}
            },
            "required": ["simplest_id", "opposite_id", "unity_justification", "developing_unity_description"]
        }
    },
    "PROPOSE_LEAP": {
        "description": "The resolution: a process that replaces the simplest and the opposite by taking both into its development (replacement), or that lets the contradiction keep existing until it is resolved (mediation).",
        "payload_schema": {
            "type": "object",
            "properties": {
                "contradiction_id": {"type": "string", "description": "ID of the Contradiction"},
                "how_resolves": {"type": "string", "description": "How this process takes in both the simplest and the opposite, or keeps their contradiction alive (e.g. 'heating is applied to this cold food')"},
                "resolution_content": {"type": "string", "description": "The resolving process itself (e.g. 'heating of the cold food'), not a recommendation or a compromise of two options"},
                "resolution_outcome": {"type": "string", "enum": ["replacement", "mediation"]}
            },
            "required": ["contradiction_id", "how_resolves", "resolution_content", "resolution_outcome"]
        }
    },
    "COMPLETE": {
        "description": "Complete the run when the goal is fully covered.",
        "payload_schema": {
            "type": "object",
            "properties": {
                "final_response": {"type": "string", "description": "The final response to the user"},
                "committed_development_refs": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "enum": ["Process", "DevelopmentRelation", "Contradiction", "PracticeAssessment"]},
                            "id": {"type": "string"}
                        },
                        "required": ["type", "id"]
                    },
                    "description": "References to the committed developments that satisfy the goal"
                },
                "evidence_observation_ids": {"type": "array", "items": {"type": "string"}, "description": "IDs of observations acting as evidence"},
                "goal_coverage": {"type": "string", "description": "How the goal is covered"},
                "why_further_development_not_needed": {"type": "string"}
            },
            "required": ["final_response", "committed_development_refs", "goal_coverage", "why_further_development_not_needed"]
        }
    }
}


for name, properties, required in [
    ("BEGIN_EXECUTION", {
        "simplest_id": {"type": "string"},
        "contradiction_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1, "uniqueItems": True},
        "resolution_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1, "uniqueItems": True},
        "execution_process_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1, "uniqueItems": True},
    }, ["simplest_id", "contradiction_ids", "resolution_ids", "execution_process_ids"]),
    ("REVISE_WORLD", {
        "observation_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        "reason": {"type": "string", "minLength": 1},
    }, ["observation_ids", "reason"]),
    ("ASSESS_LEAP", {
        "resolution_id": {"type": "string"},
        "observation_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        "explanation": {"type": "string", "minLength": 1},
    }, ["resolution_id", "observation_ids", "explanation"]),
    ("REPORT_CONTRADICTION", {
        "contested_source": {"type": "string", "minLength": 1,
                             "description": "What cannot be trusted, e.g. the output of one tool for one computation."},
        "contradicting_observation_ids": {"type": "array", "items": {"type": "string"}, "minItems": 2, "uniqueItems": True,
                                          "description": "Observations assessed 'contradicted' that show the conflict persists."},
        "supported_answer": {"type": ["string", "null"],
                             "description": "The best answer independent evidence supports, or null if none."},
        "supporting_observation_ids": {"type": "array", "items": {"type": "string"}, "uniqueItems": True,
                                       "description": "Successful, confirmed observations the answer rests on; none of them may be contradicting ones."},
        "final_response": {"type": "string", "minLength": 1,
                           "description": "States the answer (or that there is none) AND that the contested source is unreliable."},
    }, ["contested_source", "contradicting_observation_ids", "supported_answer", "supporting_observation_ids", "final_response"]),
]:
    MOVE_SPECIFICATIONS[name] = {
        "description": {"BEGIN_EXECUTION": "Accept a complete world roadmap before any tools run. List the processes along which actions will proceed.",
                        "REVISE_WORLD": "Return to planning because assessed practice requires a change to the roadmap; preserve prior versions.",
                        "ASSESS_LEAP": "Assess realization of a planned leap using successful observations from this roadmap execution.",
                        "REPORT_CONTRADICTION": "End the run honestly when practice keeps contradicting the plan across different "
                                                "attempts: name the unreliable source, cite the contradicting observations, and give "
                                                "only an answer that independent, confirmed evidence supports. The run ends as "
                                                "'unresolved', not as a success."}[name],
        "payload_schema": {"type": "object", "properties": properties, "required": required},
    }



def _nonempty_strings(schema):
    if schema.get("type") == "string":
        schema["pattern"] = r"\S"
    for child in schema.get("properties", {}).values():
        _nonempty_strings(child)
    if isinstance(schema.get("items"), dict):
        _nonempty_strings(schema["items"])

for specification in MOVE_SPECIFICATIONS.values():
    _nonempty_strings(specification["payload_schema"])


def validate_payload(move_name: str, payload: Any) -> None:
    """The same contract is shown to the proposer and enforced before every commit."""
    if move_name not in MOVE_SPECIFICATIONS:
        raise ValueError(f"Unknown move: {move_name}")
    schema = MOVE_SPECIFICATIONS[move_name]["payload_schema"]
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    if errors:
        raise ValueError(errors[0].message)


def proposal_schema(allowed_moves: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "move_type": {"type": "string", "enum": allowed_moves},
            "payload": {"type": "object"},
            # Explanations for the trace and the judge; a missing one is not worth a rejected move
            # (it cost a full model round-trip 7 times in live traces), so they are optional.
            "why_this_move_now": {"type": "string"},
            "expected_goal_contribution": {"type": "string"},
        },
        "required": ["move_type", "payload"],
        "additionalProperties": False,
    }
