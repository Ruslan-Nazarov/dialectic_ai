"""
Adapter and Runner for DialecticAI benchmark execution.
Does NOT modify any framework source code.
Adapts the shared computational tools to DialecticAI Tool/Evidence interface,
wraps execution with BenchmarkEventLogger, and supports both single-agent and Triad execution.
"""
import json
import os
import sys
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Optional
from dotenv import load_dotenv

import dialectic_ai
from dialectic_ai.core.dialectical import dialectical
from dialectic_ai.core.logger import DevelopmentLogger
import asyncio
from dialectic_ai.core.schema import AgentInput, AgentOutput, Evidence, ModelResult, ModelToolCall
from dialectic_ai.core.tool import ObservationTool
from dialectic_ai.core import OpenAILLM
from dialectic_ai.agent.base import DialecticalAgent
from dialectic_ai.engine.executor import DialecticalEngine
from dialectic_ai.engine.validator import ClaimValidator
from dialectic_ai.multi.triad import DialecticalTriad
from dialectic_ai.memory.knowledge_graph import KnowledgeGraphMemory

from experiments.framework_benchmark.events import BenchmarkEventLogger
from experiments.framework_benchmark.benchmark_case import BenchmarkCase, CASE_C
from experiments.framework_benchmark.tools import (
    calculate_statistics as core_calculate_statistics,
    compare_datasets as core_compare_datasets,
)


def normalize_tool_name(
    raw_name: str,
    event_logger: Optional[BenchmarkEventLogger] = None,
    agent_role: str = "agent",
    context: str = "native_tool_call",
) -> str:
    """
    Normalizes provider-specific namespace prefixes (e.g. 'functions.')
    to canonical benchmark tool names, logging each occurrence as an Observed event.
    """
    canonical_name = raw_name
    if raw_name.startswith("functions."):
        canonical_name = raw_name[len("functions."):]
    elif raw_name.startswith("tools."):
        canonical_name = raw_name[len("tools."):]

    if canonical_name != raw_name and event_logger:
        event_logger.record(
            event_type="tool_name_normalized",
            agent=agent_role,
            metadata={
                "raw_name": raw_name,
                "canonical_name": canonical_name,
                "context": context,
            },
        )
    return canonical_name


def normalize_text_tool_names(
    text: str,
    event_logger: Optional[BenchmarkEventLogger] = None,
    agent_role: str = "agent",
) -> str:
    """
    Normalizes 'functions.' namespaces inside textual JSON responses emitted by models,
    logging each occurrence as an Observed event.
    """
    normalized_text = text
    patterns = [
        ('"functions.calculate_statistics"', '"calculate_statistics"', "calculate_statistics"),
        ('"functions.compare_datasets"', '"compare_datasets"', "compare_datasets"),
    ]
    for raw_pat, canon_pat, canon_name in patterns:
        if raw_pat in normalized_text:
            count = normalized_text.count(raw_pat)
            normalized_text = normalized_text.replace(raw_pat, canon_pat)
            if event_logger:
                for _ in range(count):
                    event_logger.record(
                        event_type="tool_name_normalized",
                        agent=agent_role,
                        metadata={
                            "raw_name": raw_pat.strip('"'),
                            "canonical_name": canon_name,
                            "context": "text_json",
                        },
                    )
    return normalized_text


# Shared concurrency limiter (Semaphore=1) across parallel engines for Cerebras endpoint
_SHARED_CEREBRAS_SEMAPHORE: Optional[asyncio.Semaphore] = None


def get_shared_semaphore() -> asyncio.Semaphore:
    global _SHARED_CEREBRAS_SEMAPHORE
    if _SHARED_CEREBRAS_SEMAPHORE is None:
        _SHARED_CEREBRAS_SEMAPHORE = asyncio.Semaphore(1)
    return _SHARED_CEREBRAS_SEMAPHORE


class BenchmarkOpenAILLM(OpenAILLM):
    """
    Thin adapter over OpenAILLM to guarantee:
    1. temperature=0.0 and endpoint resolution;
    2. Tool name normalization (logging raw -> canonical);
    3. Concurrency limiting (Semaphore=1) to prevent burst rate limits on Cerebras;
    without modifying any code in dialectic_ai/ core.
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        timeout: int = 60,
        event_logger: Optional[BenchmarkEventLogger] = None,
        agent_role: str = "agent",
        semaphore: Optional[asyncio.Semaphore] = None,
    ):
        env_file = Path("d:/Библиотека/Исследования/Искусственный интеллект/AI_agent_hackaton/.env")
        load_dotenv(dotenv_path=env_file)
        resolved_api_key = api_key or os.getenv("CEREBRAS_API_KEY") or os.getenv("OPENAI_API_KEY", "")
        resolved_base_url = (base_url or os.getenv("CEREBRAS_BASE_URL") or os.getenv("OPENAI_BASE_URL", "https://api.cerebras.ai/v1")).rstrip("/")
        resolved_model = model or os.getenv("CEREBRAS_MODEL", "gpt-oss-120b")
        super().__init__(
            api_key=resolved_api_key,
            base_url=resolved_base_url,
            model=resolved_model,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        self.temperature = temperature
        self.event_logger = event_logger
        self.agent_role = agent_role
        self.semaphore = semaphore

    def _build_request(self, messages: list[dict], tools: list[dict] = None) -> urllib.request.Request:
        req = super()._build_request(messages, tools)
        payload = json.loads(req.data.decode("utf-8"))
        payload["temperature"] = self.temperature
        req.data = json.dumps(payload).encode("utf-8")
        return req

    async def generate(self, messages: list[dict], tools: list[dict] = None) -> str:
        sem = self.semaphore
        if sem:
            if self.event_logger:
                self.event_logger.record(
                    event_type="llm_request_wait_start",
                    agent=self.agent_role,
                    metadata={"messages_count": len(messages)},
                )
            async with sem:
                if self.event_logger:
                    self.event_logger.record(
                        event_type="llm_request_acquired",
                        agent=self.agent_role,
                        metadata={"messages_count": len(messages)},
                    )
                try:
                    raw_text = await super().generate(messages, tools)
                    norm_text = normalize_text_tool_names(raw_text, self.event_logger, self.agent_role)
                    return norm_text
                finally:
                    if self.event_logger:
                        self.event_logger.record(
                            event_type="llm_request_end",
                            agent=self.agent_role,
                        )
        else:
            raw_text = await super().generate(messages, tools)
            return normalize_text_tool_names(raw_text, self.event_logger, self.agent_role)

    async def generate_result(self, messages: list[dict], tools: list[dict] = None) -> ModelResult:
        sem = self.semaphore
        if sem:
            if self.event_logger:
                self.event_logger.record(
                    event_type="llm_request_wait_start",
                    agent=self.agent_role,
                    metadata={"messages_count": len(messages)},
                )
            async with sem:
                if self.event_logger:
                    self.event_logger.record(
                        event_type="llm_request_acquired",
                        agent=self.agent_role,
                        metadata={"messages_count": len(messages)},
                    )
                try:
                    res: ModelResult = await super().generate_result(messages, tools)
                    if res.tool_calls:
                        norm_calls = []
                        for tc in res.tool_calls:
                            norm_name = normalize_tool_name(tc.name, self.event_logger, self.agent_role, context="native_tool_call")
                            norm_calls.append(ModelToolCall(id=tc.id, name=norm_name, arguments=tc.arguments))
                        res.tool_calls = norm_calls
                    if res.text:
                        res.text = normalize_text_tool_names(res.text, self.event_logger, self.agent_role)
                    return res
                finally:
                    if self.event_logger:
                        self.event_logger.record(
                            event_type="llm_request_end",
                            agent=self.agent_role,
                        )
        else:
            res: ModelResult = await super().generate_result(messages, tools)
            if res.tool_calls:
                norm_calls = []
                for tc in res.tool_calls:
                    norm_name = normalize_tool_name(tc.name, self.event_logger, self.agent_role, context="native_tool_call")
                    norm_calls.append(ModelToolCall(id=tc.id, name=norm_name, arguments=tc.arguments))
                res.tool_calls = norm_calls
            if res.text:
                res.text = normalize_text_tool_names(res.text, self.event_logger, self.agent_role)
            return res


# --- Tool Adapters for DialecticAI ---

@dialectical(
    origin="Benchmark requirement to calculate dataset metrics",
    contradiction="LLM guessing numbers vs grounding in computed data",
    resolves="Provides verified statistics on dataset A or B",
    generates="Evidence for DialecticAI Claim verification",
    own_contradictions="Limited to summary metrics, cannot prove distribution shape",
    layer=2,
)
class DialecticCalculateStatisticsTool(ObservationTool):
    def __init__(self, event_logger: Optional[BenchmarkEventLogger] = None, producer_agent: str = "agent"):
        self._event_logger = event_logger
        self.producer_agent = producer_agent

    @property
    def name(self) -> str:
        return "calculate_statistics"

    @property
    def description(self) -> str:
        return "Calculate statistical metrics (count, mean, median, min, max, range, std_dev) for dataset 'A' or 'B'."

    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "dataset_id": {
                    "type": "string",
                    "description": "Identifier of the dataset ('A' or 'B')",
                    "enum": ["A", "B", "a", "b"],
                }
            },
            "required": ["dataset_id"],
            "additionalProperties": False,
        }

    async def execute(self, args: dict) -> Evidence:
        evidence_id = str(uuid.uuid4())
        dataset_id = args.get("dataset_id", "")
        try:
            res = core_calculate_statistics(dataset_id)
            content_str = json.dumps(res, ensure_ascii=False)
            evidence = Evidence(
                id=evidence_id,
                source=self.name,
                content=content_str,
                tool_name=self.name,
                success=True,
                tool_calls_args=args,
            )
            if self._event_logger:
                self._event_logger.record(
                    event_type="evidence_created",
                    agent=self.producer_agent,
                    tool=self.name,
                    arguments=args,
                    result=res,
                    evidence_id=evidence_id,
                    success=True,
                    metadata={"producer_agent": self.producer_agent},
                )
            return evidence
        except Exception as e:
            evidence = Evidence(
                id=evidence_id,
                source=self.name,
                content="",
                tool_name=self.name,
                success=False,
                error=str(e),
                tool_calls_args=args,
            )
            if self._event_logger:
                self._event_logger.record(
                    event_type="evidence_created",
                    agent=self.producer_agent,
                    tool=self.name,
                    arguments=args,
                    error=str(e),
                    evidence_id=evidence_id,
                    success=False,
                    metadata={"producer_agent": self.producer_agent},
                )
            return evidence


@dialectical(
    origin="Benchmark requirement to compare two datasets",
    contradiction="Comparing single mean vs full distribution differences",
    resolves="Computes exact numerical deltas between dataset A and B",
    generates="Evidence for contradiction exploration",
    own_contradictions="Does not classify relationship between datasets",
    layer=2,
)
class DialecticCompareDatasetsTool(ObservationTool):
    def __init__(self, event_logger: Optional[BenchmarkEventLogger] = None, producer_agent: str = "agent"):
        self._event_logger = event_logger
        self.producer_agent = producer_agent

    @property
    def name(self) -> str:
        return "compare_datasets"

    @property
    def description(self) -> str:
        return "Compare datasets 'A' and 'B' by calculating individual statistics and exact numerical deltas."

    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "dataset_id_a": {
                    "type": "string",
                    "description": "First dataset ID ('A')",
                    "enum": ["A", "B", "a", "b"],
                },
                "dataset_id_b": {
                    "type": "string",
                    "description": "Second dataset ID ('B')",
                    "enum": ["A", "B", "a", "b"],
                },
            },
            "required": ["dataset_id_a", "dataset_id_b"],
            "additionalProperties": False,
        }

    async def execute(self, args: dict) -> Evidence:
        evidence_id = str(uuid.uuid4())
        id_a = args.get("dataset_id_a", "")
        id_b = args.get("dataset_id_b", "")
        try:
            res = core_compare_datasets(id_a, id_b)
            content_str = json.dumps(res, ensure_ascii=False)
            evidence = Evidence(
                id=evidence_id,
                source=self.name,
                content=content_str,
                tool_name=self.name,
                success=True,
                tool_calls_args=args,
            )
            if self._event_logger:
                self._event_logger.record(
                    event_type="evidence_created",
                    agent=self.producer_agent,
                    tool=self.name,
                    arguments=args,
                    result=res,
                    evidence_id=evidence_id,
                    success=True,
                    metadata={"producer_agent": self.producer_agent},
                )
            return evidence
        except Exception as e:
            evidence = Evidence(
                id=evidence_id,
                source=self.name,
                content="",
                tool_name=self.name,
                success=False,
                error=str(e),
                tool_calls_args=args,
            )
            if self._event_logger:
                self._event_logger.record(
                    event_type="evidence_created",
                    agent=self.producer_agent,
                    tool=self.name,
                    arguments=args,
                    error=str(e),
                    evidence_id=evidence_id,
                    success=False,
                    metadata={"producer_agent": self.producer_agent},
                )
            return evidence


# --- Tracing Interceptor for DialecticAI ---

class BenchmarkDialecticLogger(DevelopmentLogger):
    """Intercepts DevelopmentLogger events to stream Observed facts into BenchmarkEventLogger."""
    def __init__(self, event_logger: BenchmarkEventLogger, agent_role: str = "agent"):
        super().__init__()
        self.event_logger = event_logger
        self.agent_role = agent_role

    async def trace_event(self, event_type: str, data: dict = None) -> None:
        await super().trace_event(event_type, data)
        payload = data or {}
        self.event_logger.record(
            event_type=f"dialectic_{event_type}",
            agent=self.agent_role,
            phase=event_type,
            metadata=payload,
        )


# --- Runner Interface ---

async def run_dialectic_single_agent(
    case: BenchmarkCase,
    llm: Any,
    event_logger: BenchmarkEventLogger,
    validator: Optional[ClaimValidator] = None,
    max_iterations: int = 5,
) -> AgentOutput:
    """
    Executes a benchmark case using a single DialecticalAgent + DialecticalEngine.
    """
    event_logger.record(event_type="run_start", metadata={"mode": "single_agent", "case_id": case.case_id})

    logger_interceptor = BenchmarkDialecticLogger(event_logger, agent_role="single_agent")
    tools = [
        DialecticCalculateStatisticsTool(event_logger=event_logger, producer_agent="single_agent"),
        DialecticCompareDatasetsTool(event_logger=event_logger, producer_agent="single_agent"),
    ]

    agent = DialecticalAgent(
        goal=case.build_user_prompt(),
        llm=llm,
        memory=KnowledgeGraphMemory(),
        tools=tools,
    )

    engine = DialecticalEngine(
        agent=agent,
        logger=logger_interceptor,
        max_iterations=max_iterations,
        validator=validator,
    )

    agent_input = AgentInput(
        user_message=case.build_user_prompt(),
        session_id=event_logger.run_id,
    )

    output = await engine.run(agent_input)

    event_logger.record(
        event_type="run_end",
        agent="single_agent",
        result=output.response,
        metadata={
            "status": output.status,
            "leap_type": output.leap_type,
            "leap_action_mismatch": output.leap_action_mismatch,
            "claims_count": len(output.claims),
            "evidence_count": len(output.evidence),
        },
    )
    return output


async def run_dialectic_triad(
    case: BenchmarkCase,
    llm: Any = None,
    event_logger: Optional[BenchmarkEventLogger] = None,
    validator: Optional[ClaimValidator] = None,
    max_iterations: int = 5,
) -> Any:
    """
    Executes a benchmark case using the DialecticalTriad (Thesis, Antithesis, Synthesis).
    """
    if event_logger:
        event_logger.record(event_type="run_start", metadata={"mode": "triad", "case_id": case.case_id})

    sem = get_shared_semaphore()

    def make_engine(role: str) -> DialecticalEngine:
        logger_sub = BenchmarkDialecticLogger(event_logger, agent_role=role) if event_logger else DevelopmentLogger()
        tools = [
            DialecticCalculateStatisticsTool(event_logger=event_logger, producer_agent=role),
            DialecticCompareDatasetsTool(event_logger=event_logger, producer_agent=role),
        ]
        role_llm = BenchmarkOpenAILLM(
            temperature=0.0,
            event_logger=event_logger,
            agent_role=role,
            semaphore=sem,
        ) if llm is None else llm
        ag = DialecticalAgent(
            goal=f"You are the {role} in a dialectical investigation.",
            llm=role_llm,
            memory=KnowledgeGraphMemory(),
            tools=tools,
        )
        engine = DialecticalEngine(agent=ag, logger=logger_sub, max_iterations=max_iterations, validator=validator)

        # Non-invasive instrumentation to record each engine's structured AgentOutput
        original_run = engine.run
        async def instrumented_run(user_input: AgentInput) -> AgentOutput:
            output: AgentOutput = await original_run(user_input)
            if event_logger:
                event_logger.record(
                    event_type="dialectic_engine_output",
                    agent=role,
                    result=output.response[:300] if output.response else "",
                    metadata={
                        "role": role,
                        "status": output.status,
                        "opposite_process": output.opposite_process,
                        "contradiction": output.contradiction,
                        "leap": output.leap,
                        "leap_type": output.leap_type,
                        "leap_action_mismatch": output.leap_action_mismatch,
                        "claims": [
                            {
                                "text": c.text,
                                "evidence_ids": c.evidence_ids,
                                "requires_validation": c.requires_validation,
                            }
                            for c in output.claims
                        ],
                        "evidence": [
                            {
                                "id": e.id,
                                "source": e.source,
                                "tool_name": e.tool_name,
                                "success": e.success,
                                "content": e.content,
                            }
                            for e in output.evidence
                        ],
                    },
                )
            return output

        engine.run = instrumented_run
        return engine

    thesis_engine = make_engine("thesis")
    antithesis_engine = make_engine("antithesis")
    synthesis_engine = make_engine("synthesis")

    triad = DialecticalTriad(
        thesis=thesis_engine,
        antithesis=antithesis_engine,
        synthesis=synthesis_engine,
    )

    session_id = event_logger.run_id if event_logger else "default_session"
    result = await triad.run(case.build_user_prompt(), session_id=session_id)

    if event_logger:
        event_logger.record(
            event_type="run_end",
            agent="triad_synthesis",
            result=result.response,
            success=result.success,
            metadata={"agent_name": result.agent_name},
        )
    return result


if __name__ == "__main__":
    import asyncio
    from pathlib import Path

    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    logger = BenchmarkEventLogger(
        run_id="dialectic_case_c_run_02",
        framework="dialectic_ai",
        case_id="CASE_C",
    )

    print("Starting DialecticAI Compatibility-Adjusted Baseline Run 02 on CASE_C with DialecticalTriad...")
    res = asyncio.run(run_dialectic_triad(
        case=CASE_C,
        llm=None,  # Will create role-specific BenchmarkOpenAILLM with shared semaphore
        event_logger=logger,
        validator=None,
        max_iterations=5,
    ))
    print("\n=== TRIAD RUN COMPLETED ===")
    print("Agent Name:", res.agent_name)
    print("Success:", res.success)
    print("Response:\n", res.response)

    results_dir = Path(__file__).resolve().parent / "results"
    results_dir.mkdir(exist_ok=True)
    out_file = results_dir / "dialectic_case_c_run_02.json"
    logger.export_json(str(out_file))
    print(f"\nEvents successfully exported to: {out_file}")
