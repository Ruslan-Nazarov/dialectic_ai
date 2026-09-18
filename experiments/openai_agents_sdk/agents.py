"""
Agents definition for the OpenAI Agents SDK experiment.
Implements a 3-tier multi-agent delegation pipeline using native Handoffs:
1. Planner / Triage Agent: analyzes the request, designs execution plan, hands off to Analysis Agent.
2. Analysis Agent: calls computational tools, inspects numbers, drafts preliminary findings, hands off to Reviewer.
3. Synthesis / Reviewer Agent: validates consistency, cross-checks numerical conclusions, produces final structured report.
"""
from typing import Any
from pydantic import BaseModel, Field
from agents import Agent, handoff
from experiments.openai_agents_sdk.tools import calculate_statistics, compare_datasets


class FinalAnalysisReport(BaseModel):
    """Structured output format produced by the Synthesis / Reviewer Agent."""
    core_thesis: str = Field(
        description="Concise answer explaining why relying solely on the mean is misleading."
    )
    numerical_evidence: dict[str, Any] = Field(
        description="Key statistics demonstrating the divergence (e.g. means, medians, ranges)."
    )
    practical_takeaway: str = Field(
        description="Practical recommendation for analysts to avoid this pitfall (e.g. inspect distribution/median)."
    )
    final_summary: str = Field(
        description="Polished, coherent, human-readable final summary for the user."
    )


def create_pipeline(
    model: str = "gpt-4o-mini",
    use_structured_output: bool = True,
) -> tuple[Agent, Agent, Agent]:
    """
    Creates the 3 agents connected via native OpenAI Agents SDK Handoffs.

    Returns:
        tuple (planner_agent, analysis_agent, reviewer_agent)
    """

    # 3. Synthesis / Reviewer Agent
    reviewer_agent = Agent(
        name="Reviewer_Agent",
        instructions=(
            "You are the Synthesis and Quality Reviewer Agent.\n"
            "Your responsibilities:\n"
            "1. Review the initial user query and the findings produced by the Analysis Agent.\n"
            "2. Verify that all numerical statements correspond directly to the tool results.\n"
            "3. Ensure the explanation is logically sound, coherent, and free of unnecessary fluff.\n"
            "4. Deliver the definitive final response to the user."
        ),
        model=model,
        output_type=FinalAnalysisReport if use_structured_output else None,
        tools=[],
        handoffs=[],  # Terminal agent in the chain; produces final output
    )

    # 2. Analysis Agent
    analysis_agent = Agent(
        name="Analysis_Agent",
        instructions=(
            "You are the Quantitative Analysis Agent.\n"
            "Your responsibilities:\n"
            "1. Execute numerical reasoning for the plan received from the Planner.\n"
            "2. ALWAYS call the available tools (`compare_datasets` or `calculate_statistics`) "
            "to compute real metrics on concrete numerical data. Never fabricate or guess metrics!\n"
            "3. Formulate raw findings highlighting the difference between mean and median/range.\n"
            "4. Once tool execution is complete and you have interpreted the results, "
            "hand off the findings to the Reviewer_Agent for final synthesis."
        ),
        model=model,
        tools=[calculate_statistics, compare_datasets],
        handoffs=[
            handoff(
                agent=reviewer_agent,
                tool_name_override="transfer_to_reviewer",
                tool_description_override="Transfer preliminary analytical results and calculated metrics to Reviewer_Agent for final synthesis.",
            )
        ],
    )

    # 1. Triage / Planner Agent
    planner_agent = Agent(
        name="Planner_Agent",
        instructions=(
            "You are the Triage and Planning Agent.\n"
            "Your responsibilities:\n"
            "1. Analyze the incoming user query.\n"
            "2. Break down the task into concrete steps: what needs to be explained, "
            "and what numerical scenario should be modeled.\n"
            "3. Formulate a short, crisp action plan.\n"
            "4. DO NOT solve the mathematical or analytical problem yourself.\n"
            "5. Immediately hand off the task and your plan to the Analysis_Agent."
        ),
        model=model,
        tools=[],
        handoffs=[
            handoff(
                agent=analysis_agent,
                tool_name_override="transfer_to_analyst",
                tool_description_override="Transfer the plan and task to Analysis_Agent for numerical analysis and tool execution.",
            )
        ],
    )

    return planner_agent, analysis_agent, reviewer_agent
