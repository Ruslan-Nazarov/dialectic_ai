# OpenAI Agents SDK — Groq Baseline Run 01 — CASE_C

**Run ID:** `openai_groq_case_c_run_01`  
**Provider:** Groq (`https://api.groq.com/openai/v1`)  
**Model:** `openai/gpt-oss-120b`  
**Temperature:** `0.0`  
**Last Agent:** `Planner_Agent`  
**Status:** `FAILURE`  

## Error Details:

```text
BadRequestError: Error code: 400 - {'error': {'message': "invalid JSON schema for tool transfer_to_analyst, tools[0].function.parameters: 'required' present but 'properties' is missing", 'type': 'invalid_request_error', 'param': 'tool transfer_to_analyst, tools[0].function.parameters'}}
```

## Final Output:

```text
[EXECUTION_FAILED] BadRequestError: Error code: 400 - {'error': {'message': "invalid JSON schema for tool transfer_to_analyst, tools[0].function.parameters: 'required' present but 'properties' is missing", 'type': 'invalid_request_error', 'param': 'tool transfer_to_analyst, tools[0].function.parameters'}}
```
