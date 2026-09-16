"""
benchmarks/bfcl/adapter.py

DIALECTICAL DESCRIPTION:
  Origin: GAIA2 ("ambiguity") tests whether an agent recognizes under-specification across a
    long, multi-step, stateful task -- a skill gated heavily by a model's planning depth, not
    by this framework's own contribution (prompt discipline, JSON robustness, repair). A free-
    tier model's weak performance there says little about whether DialecticAI itself helps.
  Contradiction: The developer needs some form of external, independently-graded evidence that
    the framework does something real -- but a benchmark that mostly measures raw model
    capability, run once, proves nothing about the framework's own contribution either.
  How it resolves: The Berkeley Function-Calling Leaderboard (BFCL) tests a single-turn,
    narrower skill this session actually hardened: given a query and a set of function schemas,
    does the model construct the right call with correctly-typed arguments? Running the SAME
    test cases through two conditions -- a bare, minimal prompt (raw baseline) and DialecticAI's
    real system prompt + parser + JsonRepairer (framework condition), both against the same
    underlying LLM -- isolates the framework's own contribution instead of just remeasuring the
    model. Grading uses BFCL's own grading algorithm (vendored verbatim in
    vendored_ast_checker.py -- see that file's own docstring for why vendored instead of
    imported live, and exactly what was and wasn't changed), not a self-written check.
  What it leads to: A same-model, same-test-case, before/after comparison an outside reader can
    verify is fair, using an independently maintained benchmark's own ground truth and grader.
  Own contradictions: Scoped to BFCL's single-turn "AST" categories only (simple/multiple/
    parallel/parallel_multiple/irrelevance) -- no live execution, no multi-turn state. This
    proves the JSON-construction layer's contribution, not the full multi-step engine's.
"""
import json
import random
import re
import uuid
from pathlib import Path
from typing import Optional

from bfcl_eval.constants.enums import Language

from benchmarks.bfcl.vendored_ast_checker import ast_checker
from dialectic_ai.agent.prompt_builder import build_system_prompt
from dialectic_ai.core.dialectical import dialectical
from dialectic_ai.core.llm import BaseLLM
from dialectic_ai.core.schema import Evidence
from dialectic_ai.core.tool import ActionTool
from dialectic_ai.engine.parser import parse_llm_response, ParseError
from dialectic_ai.engine.repair import JsonRepairer, ControlledRepairError

import bfcl_eval

BFCL_DATA_DIR = Path(bfcl_eval.__file__).parent / "data"
BFCL_POSSIBLE_ANSWER_DIR = BFCL_DATA_DIR / "possible_answer"

# Only BFCL's single-turn, no-live-execution "AST" categories -- see this module's own
# `own_contradictions` above for why multi_turn/memory/web_search/executable are out of scope.
SUPPORTED_CATEGORIES = ("simple_python", "multiple", "parallel", "parallel_multiple", "irrelevance")

# A benign, already-registered BFCL model name to satisfy internal lookups in ast_checker's
# convert_func_name() (only exercised when a function name contains "." -- none do in the
# categories above, but pass a real one anyway rather than relying on that never changing).
_BFCL_MODEL_NAME_PLACEHOLDER = "gpt-4o-2024-11-20"


class _EmptyMemory:
    """Minimal Memory-protocol stand-in: BFCL cases are single-turn, so there is no prior
    context to carry -- structurally satisfies build_system_prompt's `memory.get_context()`
    call without pulling in a real Memory implementation this benchmark doesn't need."""

    def process_turn(self, user_input, parsed_response) -> None:
        pass

    def get_context(self) -> str:
        return "No prior context (single-turn evaluation)."

    def clear(self) -> None:
        pass


def _convert_bfcl_schema(schema: dict) -> dict:
    """Translates a BFCL parameter schema (its own vocabulary: dict/integer/float/tuple) into
    standard JSON Schema, recursively, so Tool.to_prompt_description()'s json.dumps output reads
    like every other tool's schema in this framework instead of a foreign dialect."""
    if not isinstance(schema, dict):
        return schema
    type_map = {"dict": "object", "float": "number", "tuple": "array"}
    out = dict(schema)
    if "type" in out:
        out["type"] = type_map.get(out["type"], out["type"])
    if "properties" in out and isinstance(out["properties"], dict):
        out["properties"] = {k: _convert_bfcl_schema(v) for k, v in out["properties"].items()}
    if "items" in out and isinstance(out["items"], dict):
        out["items"] = _convert_bfcl_schema(out["items"])
    return out


@dialectical(
    origin="BFCL function definitions are hypothetical -- they exist only to test call "
           "construction, never to be actually invoked against a real backend.",
    contradiction="DialecticAI's Tool.execute() is a real actuator the engine actually calls; "
                  "BFCL's AST categories grade only whether the agent WOULD call correctly, "
                  "never running anything.",
    resolves="Wraps one BFCL function definition as a Tool whose parameters() is the JSON-"
             "Schema-translated version of BFCL's own schema; execute() is a harmless stub.",
    generates="Lets this framework's real prompt-building/parsing/repair pipeline run against "
              "BFCL's exact function definitions, unmodified.",
    own_contradictions="A stub execute() means this wrapper is unusable for any BFCL category "
                       "that inspects real tool-call side effects (executable/multi-turn) -- "
                       "scoped out on purpose, see SUPPORTED_CATEGORIES.",
    layer=2,
)
class BFCLFunctionTool(ActionTool):
    """Wraps one BFCL `function` definition as a DialecticAI Tool, for prompt construction only."""

    def __init__(self, func_def: dict):
        self._func_def = func_def

    @property
    def name(self) -> str:
        return self._func_def["name"]

    @property
    def description(self) -> str:
        return self._func_def.get("description", "")

    def parameters(self) -> dict:
        return _convert_bfcl_schema(
            self._func_def.get("parameters", {"type": "object", "properties": {}})
        )

    async def execute(self, args: dict) -> Evidence:
        # Never meant to be reached: AST-only grading only ever inspects the PROPOSED call,
        # not any executed result. Present only to satisfy the abstract Tool interface.
        return Evidence(
            id=str(uuid.uuid4()), source=self.name, tool_name=self.name,
            content="[BFCL: not executed -- this category grades the proposed call only]",
            success=True,
        )


def load_cases(category: str, limit: int, seed: int) -> list[dict]:
    """Loads up to `limit` test cases for `category`, deterministically sampled by `seed`, each
    merged with its ground truth. Raises FileNotFoundError if the category/possible_answer file
    is missing (fails loudly rather than silently running fewer categories than requested)."""
    data_path = BFCL_DATA_DIR / f"BFCL_v4_{category}.json"
    answer_path = BFCL_POSSIBLE_ANSWER_DIR / f"BFCL_v4_{category}.json"

    with open(data_path, encoding="utf-8") as f:
        cases = [json.loads(line) for line in f if line.strip()]

    ground_truths = {}
    if answer_path.exists():
        with open(answer_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    ground_truths[row["id"]] = row.get("ground_truth")

    sampled = random.Random(seed).sample(cases, min(limit, len(cases)))
    for case in sampled:
        case["_ground_truth"] = ground_truths.get(case["id"])
    return sampled


def _extract_question_text(case: dict) -> str:
    """BFCL's `question` field is [turn][message] -- single-turn categories have exactly one
    turn; join any user-role message content from it into the single question we ask."""
    first_turn = case["question"][0]
    return "\n".join(m["content"] for m in first_turn if m.get("role") == "user")


def _strip_code_fences(text: str) -> str:
    """Bare syntactic cleanup (not repair): strips a ```json ... ``` wrapper if present. This is
    the minimum any reasonable raw prompt would need to survive a model's habit of fencing JSON
    -- distinct from JsonRepairer's LLM-powered repair, which the raw baseline deliberately does
    not get."""
    match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    return match.group(1) if match else text


async def run_framework_turn(llm: BaseLLM, question: str, tools: list[BFCLFunctionTool]) -> Optional[list[dict]]:
    """Runs one turn through DialecticAI's real system prompt (agent/prompt_builder.py) and
    real parser/repair pipeline (engine/parser.py, engine/repair.py) -- exactly what a live
    DialecticalEngine turn would build and parse, without running the full multi-turn loop
    (unneeded here: BFCL's AST categories grade only the first proposed call).

    Returns BFCL's expected model_output shape ([{func_name: {args}}, ...]), or None on a
    parse failure the repair pass also could not fix.
    """
    system_prompt = build_system_prompt(
        goal="You are a function-calling assistant. Given the user's request and the available "
             "tools, decide which tool(s), if any, are needed to fulfill it.",
        memory=_EmptyMemory(),
        tools=tools,
        native_tool_calling=False,
    )
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": question}]
    result = await llm.generate_result(messages)
    raw_text = result.text or ""

    try:
        parsed = parse_llm_response(raw_text)
    except ParseError as e:
        try:
            parsed, _ = await JsonRepairer(llm).repair(raw_text, e)
        except ControlledRepairError:
            return None

    tool_calls = parsed.get("tool_calls") or []
    return [{tc["name"]: tc.get("args", {})} for tc in tool_calls if isinstance(tc, dict) and "name" in tc]


async def run_raw_turn(llm: BaseLLM, question: str, functions: list[dict]) -> Optional[list[dict]]:
    """Runs the same question through a bare, generic function-calling prompt -- no dialectical
    rules, no JSON repair on failure -- to isolate what the raw model alone does, as the
    baseline the framework condition is compared against.
    """
    tools_text = "\n".join(
        f"- {f['name']}({json.dumps(_convert_bfcl_schema(f.get('parameters', {})), ensure_ascii=False)}): "
        f"{f.get('description', '')}"
        for f in functions
    )
    system_prompt = (
        "You are a function-calling assistant. Given the user's request and the following "
        "available functions, decide which function(s), if any, are needed to fulfill it.\n\n"
        f"Available functions:\n{tools_text}\n\n"
        'Respond with ONLY a JSON array of function calls, no other text, in this exact format: '
        '[{"name": "<function_name>", "args": {"<arg_name>": <value>}}]\n'
        "If no function is needed, respond with an empty JSON array: []"
    )
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": question}]
    result = await llm.generate_result(messages)
    raw_text = _strip_code_fences((result.text or "").strip())

    try:
        calls = json.loads(raw_text)
    except json.JSONDecodeError:
        return None
    if not isinstance(calls, list):
        return None
    return [{c["name"]: c.get("args", {})} for c in calls if isinstance(c, dict) and "name" in c]


def grade_case(test_category: str, func_description: list[dict], model_output: Optional[list[dict]],
               possible_answer) -> bool:
    """Grades one case using BFCL's own installed ast_checker (or its documented irrelevance
    rule) -- never a self-written comparison, so the result is gradeable by BFCL's own standard.

    Matches BFCL's own eval_runner.py logic exactly: for "irrelevance", a parse failure counts
    as success too (the model failed to produce ANY function call, which is what was wanted).
    """
    contains_call = bool(model_output)
    if "irrelevance" in test_category:
        return not contains_call
    if not contains_call:
        return False
    try:
        result = ast_checker(
            func_description, model_output, possible_answer,
            Language.PYTHON, test_category, _BFCL_MODEL_NAME_PLACEHOLDER,
        )
        return bool(result.get("valid"))
    except Exception:
        return False
