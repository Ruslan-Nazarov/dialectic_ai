"""
Adapter and Runner for OpenAI Agents SDK benchmark execution.
Uses official Agent, Runner, function_tool, handoff, TracingProcessor, RunHooks.
Wraps the shared computational tools and logs events into BenchmarkEventLogger.
"""
import os
import sys
from typing import Any, Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from agents import (
    Agent,
    Runner,
    RunHooks,
    TracingProcessor,
    add_trace_processor,
    function_tool,
    handoff,
    ModelSettings,
)
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel
from openai import AsyncOpenAI

from experiments.framework_benchmark.events import BenchmarkEventLogger
from experiments.framework_benchmark.benchmark_case import BenchmarkCase, CASE_C
from experiments.framework_benchmark.tools import (
    calculate_statistics as core_calculate_statistics,
    compare_datasets as core_compare_datasets,
)


class BenchmarkStructuredReport(BaseModel):
    """Structured output format produced by Reviewer in OpenAI Agents SDK."""
    position_comparison: str = Field(description="Analysis of how Position A and Position B relate.")
    relation_classification: str = Field(description="Whether the relation is 'opposition' or 'contradiction' with justification.")
    numerical_evidence: dict[str, Any] = Field(description="Summary of facts returned by tools.")
    synthesis: str = Field(description="Final balanced synthesis resolving the question.")


def make_openai_tools(event_logger: Optional[BenchmarkEventLogger] = None):
    """Creates OpenAI Agents SDK function_tools backed by the shared benchmark computation."""
    @function_tool(
        name_override="calculate_statistics",
        description_override="Calculate statistical metrics (count, mean, median, min, max, range, std_dev) for dataset 'A' or 'B'.",
    )
    def calculate_statistics_tool(dataset_id: str) -> dict[str, Any]:
        try:
            res = core_calculate_statistics(dataset_id)
            if event_logger:
                event_logger.record(
                    event_type="tool_result",
                    tool="calculate_statistics",
                    arguments={"dataset_id": dataset_id},
                    result=res,
                    success=True,
                )
            return res
        except Exception as e:
            if event_logger:
                event_logger.record(
                    event_type="tool_result",
                    tool="calculate_statistics",
                    arguments={"dataset_id": dataset_id},
                    error=str(e),
                    success=False,
                )
            raise

    @function_tool(
        name_override="compare_datasets",
        description_override="Compare datasets 'A' and 'B' by calculating individual statistics and exact numerical deltas.",
    )
    def compare_datasets_tool(dataset_id_a: str, dataset_id_b: str) -> dict[str, Any]:
        try:
            res = core_compare_datasets(dataset_id_a, dataset_id_b)
            if event_logger:
                event_logger.record(
                    event_type="tool_result",
                    tool="compare_datasets",
                    arguments={"dataset_id_a": dataset_id_a, "dataset_id_b": dataset_id_b},
                    result=res,
                    success=True,
                )
            return res
        except Exception as e:
            if event_logger:
                event_logger.record(
                    event_type="tool_result",
                    tool="compare_datasets",
                    arguments={"dataset_id_a": dataset_id_a, "dataset_id_b": dataset_id_b},
                    error=str(e),
                    success=False,
                )
            raise

    return [calculate_statistics_tool, compare_datasets_tool]


class OpenAISDKEventHooks(RunHooks):
    """Hooks into Runner lifecycle to record Observed events in BenchmarkEventLogger."""
    def __init__(self, event_logger: BenchmarkEventLogger):
        self.event_logger = event_logger

    async def on_agent_start(self, context: Any, agent: Any) -> None:
        self.event_logger.record(event_type="agent_start", agent=agent.name)

    async def on_agent_end(self, context: Any, agent: Any, output: Any) -> None:
        self.event_logger.record(
            event_type="agent_end",
            agent=agent.name,
            result=str(output)[:200],
        )

    async def on_handoff(self, context: Any, from_agent: Any, to_agent: Any) -> None:
        self.event_logger.record(
            event_type="handoff",
            agent=from_agent.name,
            metadata={"from_agent": from_agent.name, "to_agent": to_agent.name},
        )

    async def on_tool_start(self, context: Any, agent: Any, tool: Any, call_id: str | None = None) -> None:
        self.event_logger.record(
            event_type="tool_call",
            agent=agent.name,
            tool=tool.name,
            metadata={"call_id": call_id},
        )

    async def on_tool_end(self, context: Any, agent: Any, tool: Any, result: Any, call_id: str | None = None) -> None:
        self.event_logger.record(
            event_type="tool_end",
            agent=agent.name,
            tool=tool.name,
            result=str(result)[:200],
            metadata={"call_id": call_id},
        )


class OpenAISDKTraceProcessor(TracingProcessor):
    """Tracing processor recording raw span lifecycle events."""
    def __init__(self, event_logger: BenchmarkEventLogger):
        self.event_logger = event_logger

    def on_trace_start(self, trace: Any) -> None:
        self.event_logger.record(event_type="sdk_trace_start", metadata={"trace_id": getattr(trace, "trace_id", "")})

    def on_trace_end(self, trace: Any) -> None:
        self.event_logger.record(event_type="sdk_trace_end", metadata={"trace_id": getattr(trace, "trace_id", "")})

    def on_span_start(self, span: Any) -> None:
        pass

    def on_span_end(self, span: Any) -> None:
        span_data = getattr(span, "span_data", None)
        span_type = getattr(span_data, "type", type(span_data).__name__) if span_data else "unknown"
        span_name = getattr(span_data, "name", "") if span_data else ""
        error = getattr(span, "error", None)
        self.event_logger.record(
            event_type="sdk_span_end",
            metadata={"span_type": span_type, "span_name": span_name, "error": str(error) if error else None},
        )

    def shutdown(self) -> None:
        pass

    def force_flush(self) -> None:
        pass


def resolve_default_model(model_name: Optional[str] = None) -> Any:
    """Resolves the LLM model client based on available environment credentials."""
    load_dotenv()
    if os.getenv("OPENAI_API_KEY"):
        return model_name or "gpt-4o-mini"
    if os.getenv("CEREBRAS_API_KEY"):
        client = AsyncOpenAI(
            api_key=os.getenv("CEREBRAS_API_KEY"),
            base_url=os.getenv("CEREBRAS_BASE_URL", "https://api.cerebras.ai/v1"),
        )
        return OpenAIChatCompletionsModel(
            model=model_name or os.getenv("CEREBRAS_MODEL", "gpt-oss-120b"),
            openai_client=client,
        )
    if os.getenv("GROQ_API_KEY"):
        client = AsyncOpenAI(
            api_key=os.getenv("GROQ_API_KEY"),
            base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
        )
        return OpenAIChatCompletionsModel(
            model=model_name or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            openai_client=client,
        )
    return model_name or "gpt-4o-mini"


def create_openai_pipeline(
    model: Any = None,
    event_logger: Optional[BenchmarkEventLogger] = None,
    use_structured_output: bool = True,
    model_settings: Optional[ModelSettings] = None,
) -> tuple[Agent, Agent, Agent]:
    """Creates the 3-agent delegation pipeline using native Handoffs."""
    if model is None:
        model = resolve_default_model()
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
            )
        ],
    )

    return planner, analysis, reviewer


async def run_openai_pipeline(
    case: BenchmarkCase,
    event_logger: BenchmarkEventLogger,
    model: Any = None,
    model_settings: Optional[ModelSettings] = None,
    max_turns: int = 10,
) -> Any:
    """Executes a benchmark case using OpenAI Agents SDK Runner."""
    if model is None:
        model = resolve_default_model()
    if model_settings is None:
        model_settings = ModelSettings(temperature=0.0)

    event_logger.record(event_type="run_start", metadata={"case_id": case.case_id})

    trace_proc = OpenAISDKTraceProcessor(event_logger)
    add_trace_processor(trace_proc)

    planner, analysis, reviewer = create_openai_pipeline(
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
        run_id="openai_case_c_run_01",
        framework="openai_agents_sdk",
        case_id="CASE_C",
    )
    print("Starting OpenAI Agents SDK Baseline Run on CASE_C...")
    res = asyncio.run(run_openai_pipeline(CASE_C, logger))
    print("\n=== RUN COMPLETED ===")
    print("Last Agent:", res.last_agent.name if res.last_agent else "None")
    print("Final Output:\n", res.final_output)

    results_dir = Path(__file__).resolve().parent / "results"
    results_dir.mkdir(exist_ok=True)
    out_file = results_dir / "openai_case_c_run_01.json"
    logger.export_json(str(out_file))
    print(f"\nEvents successfully exported to: {out_file}")
