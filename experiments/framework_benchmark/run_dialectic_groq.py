"""
Runner for DialecticAI on Groq provider for CASE_C benchmark (Stage 8).
Architecture: Clean DialecticalTriad (Thesis + Antithesis concurrently -> Synthesis).
Compatibility modifications explicitly OFF:
  - normalize_tool_names = False
  - limit_concurrency = False (no Semaphore)
  - arbitrary_sleeps = False
  - pacing = False
  - validator = None (Structural: ON, Semantic: OFF)
"""
import os
import sys
import json
import time
import uuid
import asyncio
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from dotenv import load_dotenv

import dialectic_ai
from dialectic_ai.core.schema import AgentInput, AgentOutput, Evidence, ModelResult, ModelToolCall
from dialectic_ai.core import OpenAILLM
from dialectic_ai.agent.base import DialecticalAgent
from dialectic_ai.engine.executor import DialecticalEngine
from dialectic_ai.multi.triad import DialecticalTriad
from dialectic_ai.memory.knowledge_graph import KnowledgeGraphMemory

from experiments.framework_benchmark.benchmark_case import CASE_C, BenchmarkCase
from experiments.framework_benchmark.events import BenchmarkEventLogger
from experiments.framework_benchmark.run_dialectic import (
    DialecticCalculateStatisticsTool,
    DialecticCompareDatasetsTool,
    BenchmarkDialecticLogger,
)


class CleanGroqOpenAILLM(OpenAILLM):
    """
    Clean OpenAILLM adapter for Groq:
    - Enforces temperature=0.0
    - NO tool name normalization (raw names passed as-is)
    - NO concurrency limiting / semaphore
    - Standard urllib transport
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "openai/gpt-oss-120b",
        temperature: float = 0.0,
        max_tokens: int = 4096,
        timeout: int = 60,
        event_logger: Optional[BenchmarkEventLogger] = None,
        agent_role: str = "agent",
    ):
        env_file = Path("d:/Библиотека/Исследования\Искусственный интеллект/AI_agent_hackaton/.env")
        load_dotenv(dotenv_path=env_file)
        resolved_api_key = api_key or os.getenv("GROQ_API_KEY", "")
        resolved_base_url = (base_url or os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")).rstrip("/")
        super().__init__(
            api_key=resolved_api_key,
            base_url=resolved_base_url,
            model=model,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        self.temperature = temperature
        self.event_logger = event_logger
        self.agent_role = agent_role

    def _build_request(self, messages: list[dict], tools: list[dict] = None) -> urllib.request.Request:
        req = super()._build_request(messages, tools)
        payload = json.loads(req.data.decode("utf-8"))
        payload["temperature"] = self.temperature
        req.data = json.dumps(payload).encode("utf-8")
        return req

    async def generate(self, messages: list[dict], tools: list[dict] = None) -> str:
        if self.event_logger:
            self.event_logger.record(
                event_type="llm_request_start",
                agent=self.agent_role,
                metadata={"messages_count": len(messages), "has_tools": bool(tools)},
            )
        res = await super().generate(messages, tools)
        if self.event_logger:
            self.event_logger.record(
                event_type="llm_request_end",
                agent=self.agent_role,
                metadata={"response_len": len(res)},
            )
        return res

    async def generate_result(self, messages: list[dict], tools: list[dict] = None) -> ModelResult:
        if self.event_logger:
            self.event_logger.record(
                event_type="llm_request_start",
                agent=self.agent_role,
                metadata={"messages_count": len(messages), "has_tools": bool(tools)},
            )
        res = await super().generate_result(messages, tools)
        if self.event_logger:
            self.event_logger.record(
                event_type="llm_request_end",
                agent=self.agent_role,
                metadata={
                    "has_tool_calls": bool(res.tool_calls),
                    "tool_calls_count": len(res.tool_calls) if res.tool_calls else 0,
                    "text_len": len(res.text) if res.text else 0,
                },
            )
        return res


async def run_clean_dialectic_triad(
    case: BenchmarkCase,
    event_logger: BenchmarkEventLogger,
    model_id: str = "openai/gpt-oss-120b",
    max_iterations: int = 5,
) -> dict[str, Any]:
    """Executes CASE_C on DialecticalTriad with Groq endpoint and non-invasive Macro Control Plane tracking."""
    event_logger.record(event_type="run_start", metadata={"mode": "clean_triad", "case_id": case.case_id})

    timings: dict[str, dict[str, Any]] = {}
    engine_outputs: dict[str, AgentOutput] = {}
    synthesis_inputs_captured: dict[str, Any] = {}

    def make_engine(role: str) -> DialecticalEngine:
        logger_sub = BenchmarkDialecticLogger(event_logger, agent_role=role)
        tools = [
            DialecticCalculateStatisticsTool(event_logger=event_logger, producer_agent=role),
            DialecticCompareDatasetsTool(event_logger=event_logger, producer_agent=role),
        ]
        role_llm = CleanGroqOpenAILLM(
            model=model_id,
            temperature=0.0,
            event_logger=event_logger,
            agent_role=role,
        )
        ag = DialecticalAgent(
            goal=f"You are the {role} in a dialectical investigation.",
            llm=role_llm,
            memory=KnowledgeGraphMemory(),
            tools=tools,
        )
        engine = DialecticalEngine(
            agent=ag,
            logger=logger_sub,
            max_iterations=max_iterations,
            validator=None,  # Baseline: Structural ON, Semantic OFF
        )

        original_run = engine.run

        async def instrumented_run(user_input: AgentInput) -> AgentOutput:
            t0 = time.time()
            iso_start = datetime.now(timezone.utc).isoformat()
            timings[role] = {"start_time": iso_start, "t0": t0}
            event_logger.record(
                event_type="engine_execution_start",
                agent=role,
                metadata={"start_time": iso_start},
            )

            if role == "synthesis":
                synthesis_inputs_captured["prompt"] = user_input.user_message
                synthesis_inputs_captured["session_id"] = user_input.session_id

            output: AgentOutput = await original_run(user_input)

            t1 = time.time()
            iso_end = datetime.now(timezone.utc).isoformat()
            timings[role]["end_time"] = iso_end
            timings[role]["t1"] = t1
            timings[role]["duration_sec"] = t1 - t0
            engine_outputs[role] = output

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
                    "start_time": iso_start,
                    "end_time": iso_end,
                    "duration_sec": t1 - t0,
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

    session_id = event_logger.run_id
    triad_result = await triad.run(case.build_user_prompt(), session_id=session_id)

    event_logger.record(
        event_type="run_end",
        agent="triad_synthesis",
        result=triad_result.response,
        success=triad_result.success,
        metadata={"agent_name": triad_result.agent_name},
    )

    # Calculate concurrency overlap
    t_start = timings.get("thesis", {}).get("t0", 0.0)
    t_end = timings.get("thesis", {}).get("t1", 0.0)
    a_start = timings.get("antithesis", {}).get("t0", 0.0)
    a_end = timings.get("antithesis", {}).get("t1", 0.0)

    overlap_sec = max(0.0, min(t_end, a_end) - max(t_start, a_start)) if t_start and a_start else 0.0

    return {
        "triad_result": triad_result,
        "timings": timings,
        "overlap_sec": overlap_sec,
        "engine_outputs": engine_outputs,
        "synthesis_inputs": synthesis_inputs_captured,
    }


async def main():
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    load_dotenv()
    groq_api_key = os.getenv("GROQ_API_KEY")
    groq_base_url = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    model_id = "openai/gpt-oss-120b"
    run_id = "dialectic_groq_case_c_run_01"

    if not groq_api_key:
        raise ValueError("GROQ_API_KEY not found in environment!")

    print("=" * 70)
    print("DIALECTICAI — GROQ CLEAN BASELINE CONFIGURATION (RUN_01)")
    print("=" * 70)
    print(f"Framework: DialecticAI")
    print(f"Mode: DialecticalTriad")
    print(f"Provider: Groq")
    print(f"Base URL: {groq_base_url}")
    print(f"Model ID: {model_id}")
    print(f"Temperature: 0.0")
    print(f"Case ID: {CASE_C.case_id}")
    print(f"Run ID: {run_id}")
    print(f"Max iterations: 5")
    print("\n--- COMPATIBILITY FEATURES STATUS ---")
    print("normalize_tool_names = False (functions.* NOT altered)")
    print("limit_concurrency = False (No Semaphore, concurrent execution)")
    print("arbitrary_sleeps = False")
    print("pacing = False")
    print("ClaimValidator = None (Structural: ON, Semantic: OFF)")
    print("=" * 70)

    logger = BenchmarkEventLogger(
        run_id=run_id,
        framework="dialectic_ai",
        case_id="CASE_C",
    )

    print(f"\n[STARTING RUN] {run_id}...")
    run_data = None
    error_message = None
    try:
        run_data = await run_clean_dialectic_triad(
            case=CASE_C,
            event_logger=logger,
            model_id=model_id,
            max_iterations=5,
        )
    except Exception as exc:
        error_message = f"{type(exc).__name__}: {exc}"
        logger.record(
            event_type="run_error",
            agent="DialecticalTriad",
            error=error_message,
        )
        logger.record(
            event_type="run_end",
            agent="DialecticalTriad",
            result=f"Failed with error: {error_message}",
        )
        print(f"\n[EXECUTION FAILED]: {error_message}")

    # Export results
    results_dir = Path(__file__).resolve().parent / "results"
    results_dir.mkdir(exist_ok=True)
    json_path = results_dir / f"{run_id}.json"
    logger.export_json(str(json_path))
    print(f"\n[SAVED] Benchmark events exported to: {json_path}")

    md_path = results_dir / f"{run_id}_final_output.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# DialecticAI — Groq Clean Baseline Run 01 — CASE_C\n\n")
        f.write(f"**Run ID:** `{run_id}`  \n")
        f.write(f"**Status:** `{'FAILURE' if error_message else 'SUCCESS'}`  \n")
        f.write(f"**Provider:** Groq (`{groq_base_url}`)  \n")
        f.write(f"**Model:** `{model_id}`  \n")
        f.write(f"**Temperature:** `0.0`  \n")
        f.write(f"**Mode:** `DialecticalTriad`  \n\n")

        if error_message:
            f.write(f"## Error Details:\n\n```text\n{error_message}\n```\n\n")

        if run_data:
            triad_result = run_data["triad_result"]
            timings = run_data["timings"]
            overlap = run_data["overlap_sec"]
            engine_outputs = run_data["engine_outputs"]
            synthesis_inputs = run_data["synthesis_inputs"]

            f.write(f"**Success:** `{triad_result.success}`  \n")
            f.write(f"**Agent Name:** `{triad_result.agent_name}`  \n\n")
            f.write(f"## Macro Timings:\n\n")
            f.write(f"- **Thesis:** {timings.get('thesis', {}).get('start_time')} → {timings.get('thesis', {}).get('end_time')} ({timings.get('thesis', {}).get('duration_sec', 0):.2f}s)\n")
            f.write(f"- **Antithesis:** {timings.get('antithesis', {}).get('start_time')} → {timings.get('antithesis', {}).get('end_time')} ({timings.get('antithesis', {}).get('duration_sec', 0):.2f}s)\n")
            f.write(f"- **Synthesis:** {timings.get('synthesis', {}).get('start_time')} → {timings.get('synthesis', {}).get('end_time')} ({timings.get('synthesis', {}).get('duration_sec', 0):.2f}s)\n")
            f.write(f"- **Concurrency Overlap:** {overlap:.2f}s\n\n")

            f.write("## Engine Responses Summary:\n\n")
            for role, out in engine_outputs.items():
                f.write(f"### {role.capitalize()} Engine\n\n")
                f.write(f"- **Status:** `{out.status}`\n")
                f.write(f"- **Opposite Process:** {out.opposite_process}\n")
                f.write(f"- **Contradiction:** {out.contradiction}\n")
                f.write(f"- **Leap:** {out.leap}\n")
                f.write(f"- **Leap Type:** `{out.leap_type}`\n")
                f.write(f"- **Leap Action Mismatch:** `{out.leap_action_mismatch}`\n")
                f.write(f"- **Claims Count:** {len(out.claims)}\n")
                f.write(f"- **Evidence Count:** {len(out.evidence)}\n\n")
                f.write(f"#### Response:\n\n```text\n{out.response}\n```\n\n")

            f.write("## Synthesis Prompt Received (Structural Inspection):\n\n")
            s_prompt = synthesis_inputs.get("prompt", "")
            f.write(f"```text\n{s_prompt}\n```\n\n")

            f.write(f"## Final Output (Synthesis Response):\n\n")
            f.write(f"```text\n{triad_result.response}\n```\n")
        else:
            f.write(f"## Final Output:\n\n```text\n[EXECUTION_FAILED] {error_message}\n```\n")

    print(f"[SAVED] Final output document saved to: {md_path}")


if __name__ == "__main__":
    asyncio.run(main())
