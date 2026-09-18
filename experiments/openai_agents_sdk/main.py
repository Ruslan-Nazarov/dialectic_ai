"""
Main entry point for the OpenAI Agents SDK experiment.
Orchestrates:
- Triage / Planner Agent
- Analysis Agent (with calculate_statistics and compare_datasets tools)
- Synthesis / Reviewer Agent (with structured FinalAnalysisReport output)
- Native TracingProcessor & RunHooks
- Error Handling demonstration
- Complete pipeline execution
"""
import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel
from agents import (
    Runner,
    RunHooks,
    TracingProcessor,
    add_trace_processor,
    enable_verbose_stdout_logging,
)
from experiments.openai_agents_sdk.agents import create_pipeline, FinalAnalysisReport
from experiments.openai_agents_sdk.tools import (
    calculate_statistics_fn,
    compare_datasets_fn,
)


if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


@dataclass
class ExperimentContext:
    """Session state carried throughout the workflow."""
    session_id: str
    user_query: str
    metadata: dict[str, Any] = field(default_factory=dict)


class CustomTraceProcessor(TracingProcessor):
    """
    Native OpenAI Agents SDK TracingProcessor.
    Captures trace and span lifecycle events across agents, tools, and handoffs.
    """
    def __init__(self):
        self.events: list[dict[str, Any]] = []

    def on_trace_start(self, trace: Any) -> None:
        self.events.append({
            "event": "trace_start",
            "trace_id": getattr(trace, "trace_id", str(trace)),
        })

    def on_trace_end(self, trace: Any) -> None:
        self.events.append({
            "event": "trace_end",
            "trace_id": getattr(trace, "trace_id", str(trace)),
        })

    def on_span_start(self, span: Any) -> None:
        span_data = getattr(span, "span_data", None)
        span_type = getattr(span_data, "type", type(span_data).__name__) if span_data else "unknown"
        span_name = getattr(span_data, "name", "") if span_data else ""
        self.events.append({
            "event": "span_start",
            "span_id": getattr(span, "span_id", None),
            "span_type": span_type,
            "span_name": span_name,
        })

    def on_span_end(self, span: Any) -> None:
        span_data = getattr(span, "span_data", None)
        span_type = getattr(span_data, "type", type(span_data).__name__) if span_data else "unknown"
        span_name = getattr(span_data, "name", "") if span_data else ""
        error = getattr(span, "error", None)
        self.events.append({
            "event": "span_end",
            "span_id": getattr(span, "span_id", None),
            "span_type": span_type,
            "span_name": span_name,
            "error": str(error) if error else None,
        })

    def shutdown(self) -> None:
        pass

    def force_flush(self) -> None:
        pass


class PipelineRunHooks(RunHooks):
    """
    Lifecycle hooks provided by OpenAI Agents SDK.
    Logs human-readable transitions between agents, tool calls, and LLM turns.
    """
    async def on_agent_start(self, context: Any, agent: Any) -> None:
        print(f"\n[SDK Hook: Agent Start] Entering: {agent.name}")

    async def on_agent_end(self, context: Any, agent: Any, output: Any) -> None:
        out_preview = str(output)[:120] + ("..." if len(str(output)) > 120 else "")
        print(f"[SDK Hook: Agent End] Exiting: {agent.name} (Output: {out_preview})")

    async def on_handoff(self, context: Any, from_agent: Any, to_agent: Any) -> None:
        print(f"[SDK Hook: Handoff] Transferring execution: {from_agent.name} -> {to_agent.name}")

    async def on_tool_start(self, context: Any, agent: Any, tool: Any, call_id: str | None = None) -> None:
        print(f"[SDK Hook: Tool Start] Agent '{agent.name}' executing tool '{tool.name}'")

    async def on_tool_end(self, context: Any, agent: Any, tool: Any, result: Any, call_id: str | None = None) -> None:
        res_preview = str(result)[:140] + ("..." if len(str(result)) > 140 else "")
        print(f"[SDK Hook: Tool End] Tool '{tool.name}' returned: {res_preview}")



def run_error_handling_demo():
    """
    Demonstrates error handling in computational tools without LLM:
    1. Empty dataset validation error.
    2. Non-numeric data type error.
    3. Proper exception handling and diagnostic message construction.
    """
    print("\n" + "=" * 70)
    print("  STAGE 9: ERROR HANDLING VERIFICATION")
    print("=" * 70)

    test_cases = [
        ("Empty list", []),
        ("Invalid element type", [10, "not_a_number", 30]),
        ("Single element dataset", [42]),
    ]

    for name, data in test_cases:
        print(f"\n[Error Case] Testing input: {name} -> {data}")
        try:
            stats = calculate_statistics_fn(data)
            print(f"  Result: Success (handled gracefully) -> {stats}")
        except (ValueError, TypeError) as exc:
            print(f"  [Intercepted Error] {type(exc).__name__}: {exc}")
            print("  [SDK Recovery Behavior] Tool raises exception -> Runner wraps error into tool response -> Model self-corrects or re-prompts.")


async def run_pipeline(user_query: str):
    """
    Runs the multi-agent pipeline using OpenAI Agents SDK Runner.
    """
    print("\n" + "=" * 70)
    print("  STAGE 10: MULTI-AGENT WORKFLOW RUN")
    print("=" * 70)
    print(f"User Query: {user_query}\n")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("[!] [NOTICE] OPENAI_API_KEY environment variable is not set.")
        print("   In accordance with experiment constraints:")
        print("   - No dummy keys will be substituted.")
        print("   - Showing offline pipeline validation, simulated execution trail, and deterministic numerical results.")
        print("\n--- DETERMINISTIC NUMERICAL DEMO (Tool Execution) ---")

        # Symmetric group vs Skewed group
        group_symmetric = [48, 49, 50, 51, 52]
        group_skewed = [10, 10, 10, 10, 210]

        print("Dataset 1 (Symmetric):", group_symmetric)
        print("Dataset 2 (Skewed):   ", group_skewed)

        stats_sym = calculate_statistics_fn(group_symmetric)
        stats_skew = calculate_statistics_fn(group_skewed)
        comp = compare_datasets_fn(group_symmetric, group_skewed, "Symmetric Group", "Skewed Group")

        print("\nTool Output [calculate_statistics] for Group 1:")
        print(json.dumps(stats_sym, indent=2))
        print("\nTool Output [calculate_statistics] for Group 2:")
        print(json.dumps(stats_skew, indent=2))
        print("\nTool Output [compare_datasets]:")
        print(json.dumps(comp, indent=2))

        print("\n--- SIMULATED RUNNER AGENT TRACE ---")
        print("1. User Query -> Planner_Agent")
        print("   Planner action: Formulates task breakdown: (a) explain mean vs distribution, (b) generate two datasets with identical mean=50, (c) handoff to Analysis_Agent.")
        print("   SDK Event: Handoff -> Planner_Agent transferred to Analysis_Agent.")
        print("2. Analysis_Agent -> Invokes tool `compare_datasets(dataset_a=[48, 49, 50, 51, 52], dataset_b=[10, 10, 10, 10, 210])`")
        print("   Tool result received: Both means = 50.0. Medians = 50.0 vs 10.0. Ranges = 4.0 vs 200.0.")
        print("   Analysis_Agent synthesis: Drafts preliminary observation: single mean (50.0) completely obscures that 80% of the skewed dataset is <= 10.")
        print("   SDK Event: Handoff -> Analysis_Agent transferred to Reviewer_Agent.")
        print("3. Reviewer_Agent -> Synthesizes final response and validates against numerical evidence.")
        print("   Final output generated in structured schema (FinalAnalysisReport).")
        return

    # Real OpenAI API Run if key is present
    trace_processor = CustomTraceProcessor()
    add_trace_processor(trace_processor)

    planner, analysis, reviewer = create_pipeline(model="gpt-4o-mini", use_structured_output=True)
    hooks = PipelineRunHooks()

    context = ExperimentContext(
        session_id="exp_session_001",
        user_query=user_query,
    )

    print("[*] Starting OpenAI Agents SDK Runner...")
    result = await Runner.run(
        starting_agent=planner,
        input=user_query,
        context=context,
        hooks=hooks,
        max_turns=12,
    )

    print("\n" + "=" * 70)
    print("  WORKFLOW COMPLETED SUCCESSFULLY")
    print("=" * 70)
    print(f"Final Agent: {result.last_agent.name if result.last_agent else 'Unknown'}")
    print("\nStructured Final Output:")
    if isinstance(result.final_output, BaseModel):
        print(json.dumps(result.final_output.model_dump(), indent=2, ensure_ascii=False))
    else:
        print(result.final_output)

    print("\nCaptured Tracing Spans:")
    for ev in trace_processor.events:
        print(f"  [{ev.get('event')}] {ev.get('span_type')} - {ev.get('span_name')} (error: {ev.get('error')})")


def main():
    query = (
        "Объясни, почему использование одного среднего значения может вводить в заблуждение "
        "при анализе двух сильно различающихся групп данных, и покажи это на простом численном примере."
    )

    # 1. Error Handling Check
    run_error_handling_demo()

    # 2. Main Workflow Execution
    asyncio.run(run_pipeline(query))


if __name__ == "__main__":
    main()
