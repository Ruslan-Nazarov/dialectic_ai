"""
dialectic_ai/engine/executor.py

DIALECTICAL DESCRIPTION:
  Where it came from: The Agent (Layer 1) can think, Reality (Layer 2) can check.
    But no one forces them to interact. An orchestrator is needed.
  Contradiction: Without a forced cycle, a developer may accidentally write
    an agent that responds directly, bypassing reality check. Rule 3
    (Collision with the world) exists only on paper.
  How it resolves: DialecticalEngine is the physical embodiment of the dialectical cycle
    in code. It runs a while-loop, intercepts tool_calls, forcibly
    performs RealityCheck, and returns Observation to the agent. The agent CANNOT provide
    an answer without going through the Collision phase — if tools are requested.
  What it leads to: DevelopmentLogger writes a trace of each cycle. The Observability
    dashboard reads this trace and visualizes the entire path of the agent.
  Own contradictions: The forced cycle creates latency — each tool call = additional LLM request. 
    The agent may get stuck in an infinite loop of tool_calls. max_iterations is a safety net, not a solution.
"""
import json
from dialectic_ai.core.dialectical import dialectical
from dialectic_ai.core.schema import AgentInput, AgentOutput, MemoryUpdate, Evidence, Claim, Hypothesis
from dialectic_ai.core.logger import DevelopmentLogger
from dialectic_ai.engine.parser import parse_llm_response, ParseError
from dialectic_ai.engine.validator import ClaimValidator
import asyncio
import uuid


@dialectical(
    origin="The Agent can think, Reality can check. No one has forcibly connected them together",
    contradiction="Without the engine, Rule 3 (Collision) is just words. The developer can "
                  "accidentally bypass it. Rules are not enforced without enforcement",
    resolves="Physically implements the dialectical cycle: generate → collide → synthesize. "
             "The agent cannot provide a response while there are unverified tool_calls",
    generates="Observability (tracing, dashboard): each step of the cycle is logged. "
              "Multi-agent (Layer 4): The Engine becomes a unit that can be delegated",
    own_contradictions="Each tool call = additional LLM request = latency + cost. "
                       "max_iterations is a workaround. A smart stop (convergence detection) is needed",
    layer=3,
)
class DialecticalEngine:
    """
    Orchestrator of the agent's dialectical cycle.

    Forcibly executes the cycle:
      1. _phase_generate()  — LLM forms intention (thought + tool_calls or response)
      2. _phase_collide()   — intercepts tool_calls, runs RealityCheck, gets observation
      3. _phase_synthesize() — LLM receives observation and forms final response
      4. _phase_validate()  — Checks claims against evidence

    Example usage:
        engine = DialecticalEngine(agent, logger=DevelopmentLogger())
        output = engine.run(AgentInput(user_message="Here is my code: ..."))
        print(output.response)
    """

    def __init__(
        self,
        agent,  # DialecticalAgent
        logger: DevelopmentLogger = None,
        max_iterations: int = 5,
        validator: ClaimValidator = None,
    ):
        self.agent = agent
        self.logger = logger or DevelopmentLogger()
        self.max_iterations = max_iterations
        self.validator = validator

        # Building the tool registry: name -> Tool
        self._tool_registry = {t.name: t for t in agent.tools}

    async def run(self, user_input: AgentInput) -> AgentOutput:
        """
        Runs the full dialectical cycle for a single user message.

        Returns:
            AgentOutput with the final response and all observations
        """
        print(f"\n{'='*60}")
        print(f"  [Engine] New message: {user_input.user_message[:80]}")
        print(f"{'='*60}")

        await self.agent.add_to_history("user", user_input.user_message)

        await self.logger.trace_event("engine_start", {
            "session_id": user_input.session_id,
            "user_message": user_input.user_message[:200],
        })

        all_evidence: list[Evidence] = []
        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1
            print(f"\n  [Iteration {iteration}] Requesting LLM...")

            parsed = await self._phase_generate(user_input, iteration)
            if not parsed:
                continue

            tool_calls = parsed.get("tool_calls", [])
            if tool_calls:
                observation_message = await self._phase_collide(user_input, iteration, tool_calls, all_evidence)
                await self.agent.add_to_history("assistant", json.dumps(parsed, ensure_ascii=False))
                await self.agent.add_to_history("user", f"Observation from tools:\n{observation_message}")
                continue

            response_text = parsed.get("response", "")
            if response_text:
                agent_output = await self._phase_synthesize(user_input, iteration, parsed, all_evidence)
                
                # Phase 4 Validate
                validation_errors = await self._phase_validate(agent_output.claims, all_evidence, user_input.session_id)
                if validation_errors:
                    err_msg = "Your claims did not pass validation:\n- " + "\n- ".join(validation_errors) + "\nPlease correct your response."
                    print(f"  [Validation] ERROR: {len(validation_errors)} discrepancies.")
                    await self.agent.add_to_history("assistant", json.dumps(parsed, ensure_ascii=False))
                    await self.agent.add_to_history("user", err_msg)
                    await self.logger.trace_event("validation_failed", {
                        "session_id": user_input.session_id,
                        "iteration": iteration,
                        "errors": validation_errors,
                    })
                    continue

                print("  [Validation] Successfully passed.")
                return agent_output

        await self.logger.trace_event("max_iterations_reached", {"iterations": self.max_iterations})
        return AgentOutput(
            response="[Engine] Maximum number of iterations exceeded. The agent could not generate a response.",
            thought="",
            is_final=True,
        )

    async def _phase_generate(self, user_input: AgentInput, iteration: int) -> dict | None:
        tools_payload = None
        if self._tool_registry:
            tools_payload = []
            for name, tool in self._tool_registry.items():
                tools_payload.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters()
                    }
                })
                
        raw_response = await self.agent.llm.generate(self.agent.get_messages(), tools=tools_payload)
        try:
            parsed = parse_llm_response(raw_response)
        except ParseError as e:
            print(f"  [!] Parsing error: {e}")
            await self.logger.trace_event("parse_error", {
                "session_id": user_input.session_id,
                "error": str(e),
                "raw": raw_response[:200],
            })
            await self.agent.add_to_history("user", "Error: your response is not valid JSON. Please respond strictly in JSON format.")
            return None

        thought = parsed.get("thought", "")
        hyp_raw = parsed.get("hypothesis")
        
        if hyp_raw:
            print(f"  [Hypothesis] {hyp_raw.get('assumption', '')}")
            if hyp_raw.get("plan_steps"):
                print(f"  [Plan] " + ", ".join(hyp_raw.get("plan_steps", [])))

        print(f"  [Thought] {thought[:100]}")
        await self.logger.trace_event("generate", {
            "session_id": user_input.session_id,
            "iteration": iteration,
            "hypothesis": hyp_raw,
            "thought": thought,
            "tool_calls_count": len(parsed.get("tool_calls", [])),
            "has_response": bool(parsed.get("response")),
        })
        return parsed

    async def _phase_collide(self, user_input: AgentInput, iteration: int, tool_calls: list, all_evidence: list) -> str:
        observation_parts = []
        tool_tasks = []

        for call in tool_calls:
            tool_name = call.get("name", "")
            tool_args = call.get("args", {})

            await self.logger.trace_event("tool_call", {
                "session_id": user_input.session_id,
                "iteration": iteration,
                "tool": tool_name,
                "args": tool_args,
            })

            if tool_name not in self._tool_registry:
                obs = f"[Error] Tool '{tool_name}' is not registered."
                print(f"  [!] {obs}")
                observation_parts.append(obs)
            else:
                print(f"  [Collision] Running '{tool_name}'...")
                task = self._tool_registry[tool_name].execute(tool_args)
                tool_tasks.append((tool_name, task))

        if tool_tasks:
            results = await asyncio.gather(*(t[1] for t in tool_tasks), return_exceptions=True)
            for i, result in enumerate(results):
                tool_name = tool_tasks[i][0]
                
                if isinstance(result, Exception):
                    result = Evidence(
                        id=str(uuid.uuid4()),
                        source=tool_name,
                        content="",
                        tool_name=tool_name,
                        success=False,
                        error=f"Unhandled tool exception: {result}"
                    )

                all_evidence.append(result)
                await self.logger.log_collision(
                    tool_name,
                    result.success,
                    str(result.content) if result.success else str(result.error),
                    session_id=user_input.session_id,
                )

                if result.success:
                    obs = f"[Evidence ID: {result.id} | Tool '{tool_name}'] Result:\n{result.content}"
                else:
                    obs = f"[Evidence ID: {result.id} | Tool '{tool_name}'] Error:\n{result.error}"

                print(f"  [Observation] {obs[:150]}")
                observation_parts.append(obs)

        return "\n\n".join(observation_parts)

    async def _phase_synthesize(self, user_input: AgentInput, iteration: int, parsed: dict, all_evidence: list) -> AgentOutput:
        response_text = parsed.get("response", "")
        self.agent.memory.process_turn(user_input, parsed)
        
        memory_updates = [
            MemoryUpdate(
                concept=u.get("concept", ""),
                status=u.get("status", "unknown"),
            )
            for u in parsed.get("knowledge_updates", [])
            if u.get("concept")
        ]

        await self.agent.add_to_history("assistant", response_text)

        await self.logger.trace_event("synthesize", {
            "session_id": user_input.session_id,
            "iteration": iteration,
            "response_preview": response_text[:200],
            "memory_updates": len(memory_updates),
            "memory_updated": len(memory_updates) > 0,
        })

        print(f"\n  [Synthesis] {response_text[:200]}")

        claims = [
            Claim(
                text=c.get("text", ""),
                evidence_ids=c.get("evidence_ids", []),
                requires_validation=c.get("requires_validation", False)
            ) for c in parsed.get("claims", []) if c.get("text")
        ]
        
        hyp_raw = parsed.get("hypothesis")
        hypothesis = None
        if hyp_raw:
            hypothesis = Hypothesis(
                assumption=hyp_raw.get("assumption", ""),
                plan_steps=hyp_raw.get("plan_steps", [])
            )

        return AgentOutput(
            response=response_text,
            thought=parsed.get("thought", ""),
            hypothesis=hypothesis,
            claims=claims,
            memory_updates=memory_updates,
            evidence=all_evidence,
            is_final=True,
        )

    async def _phase_validate(self, claims: list[Claim], all_evidence: list[Evidence], session_id: str) -> list[str]:
        validation_errors = []
        known_evidence_ids = {e.id for e in all_evidence}

        for claim in claims:
            for eid in claim.evidence_ids:
                if eid not in known_evidence_ids:
                    validation_errors.append(f"Claim '{claim.text}' refers to unknown evidence_id '{eid}'.")
            
            if claim.requires_validation and self.validator:
                val_err = await self.validator.validate(claim, all_evidence, session_id=session_id)
                if val_err:
                    validation_errors.append(val_err)
                    
        return validation_errors
