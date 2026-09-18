from typing import Dict, Any

CASES = [
    {
        "id": "case_1",
        "name": "CASE 1 - Valid Development",
        "user_request": "I have a new item with numeric_value of 15. Determine whether this item belongs to category X according to our standard threshold rules.",
        "execution_inputs": {"numeric_value": 15},
        "registry_tools": [
            {
                "name": "classify_item_by_rule",
                "description": "Classifies an item into category X if numeric_value >= 10, else Y.",
                "input_schema": {"numeric_value": "float"},
                "output_schema": {"classified": "bool", "category": "str", "confidence": "float"},
                "executor": lambda x: {"classified": True, "category": "X" if x.get("numeric_value", 0) >= 10 else "Y", "confidence": 1.0}
            }
        ],
        "expected_control": {
            "task_success": True
        },
        "expected_v1": {
            "valid_development": True,
            "opposite_detected": True,
            "contradiction_constructed": True,
            "goal_sufficiency": True,
            "execution_run": True
        }
    },
    {
        "id": "case_2",
        "name": "CASE 2 - Workflow-as-Development Trap",
        "user_request": "Read temperature from sensor. Compare it to the 100 degree threshold. If higher, trigger the alarm.",
        "execution_inputs": {"temperature": 105},
        "registry_tools": [
            {
                "name": "sensor_control",
                "description": "Reads temperature and triggers alarm if needed",
                "input_schema": {"temperature": "float"},
                "output_schema": {"alarm_triggered": "bool"},
                "executor": lambda x: {"alarm_triggered": x.get("temperature", 0) > 100}
            }
        ],
        "expected_control": {
            "task_success": True
        },
        "expected_v1": {
            # Expected not to be validated as semantic development, since it's just steps.
            # It might just fail development validation.
            "valid_development": False,
            "opposite_detected": False,
            "contradiction_constructed": False,
            "goal_sufficiency": False,
            "execution_run": False
        }
    },
    {
        "id": "case_3",
        "name": "CASE 3 - Alternative Implementation Trap",
        "user_request": "Fetch user data. You can either use the SQL implementation or the NoSQL implementation, they both work.",
        "execution_inputs": {"user_id": 1},
        "registry_tools": [
            {
                "name": "fetch_user_sql",
                "description": "Fetches user data from SQL",
                "input_schema": {"user_id": "int"},
                "output_schema": {"data": "str"},
                "executor": lambda x: {"data": "SQL_DATA"}
            },
            {
                "name": "fetch_user_nosql",
                "description": "Fetches user data from NoSQL",
                "input_schema": {"user_id": "int"},
                "output_schema": {"data": "str"},
                "executor": lambda x: {"data": "NOSQL_DATA"}
            }
        ],
        "expected_control": {
            "task_success": True
        },
        "expected_v1": {
            "valid_development": True, # It might accept them as processes
            "opposite_detected": False, # But replacement/substitutability != opposite
            "contradiction_constructed": False
        }
    },
    {
        "id": "case_4",
        "name": "CASE 4 - Contradiction not required for execution",
        "user_request": "Calculate the factorial of 5. You could do it by manual expansion or by the recursive formula.",
        "execution_inputs": {"n": 5},
        "registry_tools": [
            {
                "name": "calculate_factorial",
                "description": "Calculates factorial of a number",
                "input_schema": {"n": "int"},
                "output_schema": {"result": "int"},
                "executor": lambda x: {"result": 120} # Fake executor for simplicity
            }
        ],
        "expected_control": {
            "task_success": True
        },
        "expected_v1": {
            "valid_development": True,
            "opposite_detected": True,
            "contradiction_constructed": True,
            "goal_sufficiency": True, # Contradiction exists but doesn't block execution
            "execution_run": True
        }
    },
    {
        "id": "case_5",
        "name": "CASE 5 - Blocking Contradiction",
        # We need a controlled synthetic scenario where P2 excludes P0 and contradiction blocks the goal.
        # "Achieve 100% data anonymization but also provide full original personalized user analytics."
        "user_request": "Create a report that completely anonymizes all user data so no one can be identified, and also lists the exact names and purchases of every individual user for personalized marketing.",
        "execution_inputs": {},
        "registry_tools": [
            {
                "name": "generate_report",
                "description": "Generates a report",
                "input_schema": {},
                "output_schema": {"report": "str"},
                "executor": lambda x: {"report": "done"}
            }
        ],
        "expected_control": {
            "task_success": True # Control will probably just ignorantly execute or give a generic answer
        },
        "expected_v1": {
            "valid_development": True,
            "opposite_detected": True,
            "contradiction_constructed": True,
            "goal_sufficiency": False, # MUST FAIL - conflicting requirements
            "execution_run": False
        }
    },
    {
        "id": "case_6",
        "name": "CASE 6 - Operational Failure",
        "user_request": "I have a new item with numeric_value of 15. Determine whether this item belongs to category X according to our standard threshold rules.",
        "execution_inputs": {"numeric_value": 15},
        "registry_tools": [
            # Registry intentionally empty or missing the required tool
        ],
        "expected_control": {
            "task_success": False
        },
        "expected_v1": {
            "valid_development": True,
            "opposite_detected": True,
            "contradiction_constructed": True,
            "goal_sufficiency": True,
            "execution_run": False # Fails operationally
        }
    }
]
