"""
Execution script for OpenAI Agents SDK on Groq provider for CASE_C benchmark.
Stage 7A: Compatibility-adjusted baseline (run_02).
Uses official handoff(input_type=HandoffPayload, on_handoff=...) to avoid empty schema rejected by Groq.
No pacing, no semaphore, no prompt modifications, no forced transitions.
"""
import os
import sys
import json
import asyncio
from pathlib import Path
from typing import Any, Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field

import agents
from agents import (
    Agent,
    Runner,
    handoff,
    ModelSettings,
    add_trace_processor,
)
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel, Converter
from openai import AsyncOpenAI

from experiments.framework_benchmark.benchmark_case import CASE_C, BenchmarkCase
from experiments.framework_benchmark.events import BenchmarkEventLogger
from experiments.framework_benchmark.run_openai_sdk import (
    make_openai_tools,
    OpenAISDKEventHooks,
    OpenAISDKTraceProcessor,
    BenchmarkStructuredReport,
)


class HandoffPayload(BaseModel):
    """Minimal transport payload for OpenAI Agents SDK handoffs to avoid empty JSON schema."""
    reason: str = Field(description="Reason for handing off to the target agent.")


def handle_handoff(ctx: Any, input_data: HandoffPayload) -> None:
    """No-op callback required by Agents SDK when input_type is provided."""
    pass


def create_groq_pipeline(
    model: Any,
    event_logger: Optional[BenchmarkEventLogger] = None,
    use_structured_output: bool = True,
    model_settings: Optional[ModelSettings] = None,
) -> tuple[Agent, Agent, Agent]:
    """Creates the 3-agent delegation pipeline with compatibility-adjusted handoff schemas."""
    if model_settings is None:
        model_settings = ModelSettings(temperature=0.0)

    tools = make_openai_tools(event_logger)

    reviewer = Agent(
        name="Reviewer_Agent",
        instructions=(
            "You are the Synthesis and Reviewer Agent. "
            "Review the initial positions, examine the numerical tool outputs received from Analysis_Agent, "
            "explicitly classify whether the positions represent a non-contradictory opposition (different aspects) "
            "or a direct logical contradiction, and produce the final coherent synthesis."
        ),
        model=model,
        model_settings=model_settings,
        output_type=BenchmarkStructuredReport if use_structured_output else None,
        tools=[],
        handoffs=[],
    )

    analysis = Agent(
        name="Analysis_Agent",
        instructions=(
            "You are the Quantitative Analysis Agent. "
            "You MUST call the available tools (`compare_datasets` or `calculate_statistics`) "
            "using dataset IDs 'A' and 'B' to obtain concrete statistical metrics. "
            "Do NOT speculate or fabricate numbers. Once calculations are complete, hand off "
            "the findings to Reviewer_Agent."
        ),
        model=model,
        model_settings=model_settings,
        tools=tools,
        handoffs=[
            handoff(
                agent=reviewer,
                tool_name_override="transfer_to_reviewer",
                tool_description_override="Transfer calculated metrics to Reviewer_Agent for synthesis.",
                input_type=HandoffPayload,
                on_handoff=handle_handoff,
            )
        ],
    )

    planner = Agent(
        name="Planner_Agent",
        instructions=(
            "You are the Triage and Planning Agent. "
            "Analyze the benchmark task, lay out the steps for examining Position A and Position B, "
            "do NOT perform numerical calculations yourself, and immediately hand off to Analysis_Agent."
        ),
        model=model,
        model_settings=model_settings,
        tools=[],
        handoffs=[
            handoff(
                agent=analysis,
                tool_name_override="transfer_to_analyst",
                tool_description_override="Transfer execution plan to Analysis_Agent for tool execution.",
                input_type=HandoffPayload,
                on_handoff=handle_handoff,
            )
        ],
    )

    return planner, analysis, reviewer


async def run_groq_pipeline(
    case: BenchmarkCase,
    event_logger: BenchmarkEventLogger,
    model: Any,
    model_settings: Optional[ModelSettings] = None,
    max_turns: int = 10,
) -> Any:
    if model_settings is None:
        model_settings = ModelSettings(temperature=0.0)

    event_logger.record(event_type="run_start", metadata={"case_id": case.case_id})

    trace_proc = OpenAISDKTraceProcessor(event_logger)
    add_trace_processor(trace_proc)

    planner, analysis, reviewer = create_groq_pipeline(
        model=model,
        event_logger=event_logger,
        use_structured_output=True,
        model_settings=model_settings,
    )
    hooks = OpenAISDKEventHooks(event_logger)

    result = await Runner.run(
        starting_agent=planner,
        input=case.build_user_prompt(),
        hooks=hooks,
        max_turns=max_turns,
    )

    event_logger.record(
        event_type="run_end",
        agent=result.last_agent.name if result.last_agent else "unknown",
        result=str(result.final_output)[:300],
    )
    return result


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
    run_id = "openai_groq_case_c_run_02"

    if not groq_api_key:
        raise ValueError("GROQ_API_KEY not found in environment!")

    client = AsyncOpenAI(
        api_key=groq_api_key,
        base_url=groq_base_url,
    )
    model = OpenAIChatCompletionsModel(
        model=model_id,
        openai_client=client,
    )

    # Instantiate pipeline to inspect handoff schemas
    planner, analysis, reviewer = create_groq_pipeline(model=model)
    analyst_tool = Converter.convert_handoff_tool(planner.handoffs[0])
    reviewer_tool = Converter.convert_handoff_tool(analysis.handoffs[0])

    print("=" * 70)
    print("OPENAI AGENTS SDK — GROQ COMPATIBILITY-ADJUSTED BASELINE (RUN_02)")
    print("=" * 70)
    print(f"SDK version: agents {getattr(agents, '__version__', '0.22.2')}")
    print(f"Provider: Groq")
    print(f"Base URL: {groq_base_url}")
    print(f"Model ID: {model_id}")
    print(f"Temperature: 0.0")
    print(f"Case ID: {CASE_C.case_id}")
    print(f"Run ID: {run_id}")
    print("Agents: Planner_Agent -> Analysis_Agent -> Reviewer_Agent")
    print("Handoff mechanism: handoff(input_type=HandoffPayload, on_handoff=...)")
    print("=" * 70)

    print("\n--- SCHEMA INSPECTION: transfer_to_analyst ---")
    print(json.dumps(analyst_tool, indent=2))
    print("\n--- SCHEMA INSPECTION: transfer_to_reviewer ---")
    print(json.dumps(reviewer_tool, indent=2))
    print("=" * 70)

    # Verification: Ensure schemas are non-empty
    analyst_params = analyst_tool.get("function", {}).get("parameters", {})
    reviewer_params = reviewer_tool.get("function", {}).get("parameters", {})
    if not analyst_params.get("properties") or not reviewer_params.get("properties"):
        print("[FATAL] Handoff schema properties are empty! STOPPING execution as instructed.")
        sys.exit(1)

    print("\n[VERIFICATION PASSED]: Both handoff schemas contain non-empty properties.")

    logger = BenchmarkEventLogger(
        run_id=run_id,
        framework="openai_agents_sdk",
        case_id="CASE_C",
    )

    print(f"\n[STARTING RUN] {run_id}...")
    error_message = None
    last_agent_name = "None"
    final_output = ""
    result = None
    try:
        result = await run_groq_pipeline(
            case=CASE_C,
            event_logger=logger,
            model=model,
            model_settings=ModelSettings(temperature=0.0),
            max_turns=10,
        )
        last_agent_name = result.last_agent.name if result.last_agent else "Unknown"
        final_output = result.final_output
    except Exception as exc:
        error_message = f"{type(exc).__name__}: {exc}"
        last_agent_name = "Unknown"
        final_output = f"[EXECUTION_FAILED] {error_message}"
        logger.record(
            event_type="run_error",
            agent="Unknown",
            error=error_message,
        )
        logger.record(
            event_type="run_end",
            agent="Unknown",
            result=f"Failed with error: {error_message}",
        )
        print(f"\n[EXECUTION FAILED]: {error_message}")

    print("\n" + "=" * 70)
    print("[RUN COMPLETED]")
    print(f"Last Agent: {last_agent_name}")
    print("=" * 70)
    print("Final Output:\n", final_output)
    print("=" * 70)

    # Structural history inspection
    input_items_summary = []
    if result is not None:
        try:
            items = result.to_input_list()
            print(f"\n[STRUCTURAL HISTORY INSPECTION] Total input items in conversation: {len(items)}")
            for i, item in enumerate(items):
                item_type = type(item).__name__
                role = getattr(item, "role", getattr(item, "type", "unknown"))
                summary = f"Item {i} ({item_type}, role={role})"
                if hasattr(item, "content"):
                    summary += f": content_len={len(str(item.content))}"
                input_items_summary.append(summary)
                print(f"  - {summary}")
        except Exception as e:
            print(f"Error inspecting input list: {e}")

    # Export results
    results_dir = Path(__file__).resolve().parent / "results"
    results_dir.mkdir(exist_ok=True)
    json_path = results_dir / f"{run_id}.json"
    logger.export_json(str(json_path))
    print(f"\n[SAVED] Benchmark events exported to: {json_path}")

    md_path = results_dir / f"{run_id}_final_output.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# OpenAI Agents SDK — Groq Compatibility-Adjusted Baseline Run 02 — CASE_C\n\n")
        f.write(f"**Run ID:** `{run_id}`  \n")
        f.write(f"**Status:** `{'FAILURE' if error_message else 'SUCCESS'}`  \n")
        f.write(f"**Provider:** Groq (`{groq_base_url}`)  \n")
        f.write(f"**Model:** `{model_id}`  \n")
        f.write(f"**Temperature:** `0.0`  \n")
        f.write(f"**Last Agent:** `{last_agent_name}`  \n\n")
        if error_message:
            f.write(f"## Error Details:\n\n```text\n{error_message}\n```\n\n")
        if input_items_summary:
            f.write(f"## Structural Input Items ({len(input_items_summary)} items):\n\n")
            for s in input_items_summary:
                f.write(f"- {s}\n")
            f.write("\n")
        f.write(f"## Final Output:\n\n")
        if isinstance(final_output, BaseModel):
            f.write(f"```json\n{json.dumps(final_output.model_dump(), indent=2, ensure_ascii=False)}\n```\n")
        else:
            f.write(f"```text\n{final_output}\n```\n")

    print(f"[SAVED] Final output document saved to: {md_path}")


if __name__ == "__main__":
    asyncio.run(main())
