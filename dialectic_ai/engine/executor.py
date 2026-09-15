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
from dialectic_ai.engine.repair import JsonRepairer, ControlledRepairError
from dialectic_ai.engine.evidence_store import EvidenceStore
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
    simplest_process="A single agent turn: form a hypothesis, then answer.",
    opposite_process="Answering directly from the hypothesis without ever calling a tool — "
                     "a process that needs no Reality Check at all to produce an answer.",
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
        debug_mode: bool = False,
    ):
        self.agent = agent
        self.logger = logger or DevelopmentLogger()
        self.max_iterations = max_iterations
        self.validator = validator
        self.debug_mode = debug_mode

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

        same_thought_counter = 0
        last_thought = ""

        await self.logger.trace_event("engine_start", {
            "session_id": user_input.session_id,
            "user_message": user_input.user_message[:200],
        })

        evidence_store = EvidenceStore()
        validation_retries = 0
        last_failed_call_signature = None
        repeated_failure_count = 0
        leap_mismatch_retries = 0

        for iteration in range(1, self.max_iterations + 1):
            print(f"\n  [Iteration {iteration}] Requesting LLM...")

            parsed = await self._phase_generate(user_input, iteration)
            if not parsed:
                continue

            if self.debug_mode:
                print(f"\n  [DEBUG] Hypothesis: {parsed.get('hypothesis')}")
                print(f"  [DEBUG] Decision: {parsed.get('decision', '')}")
                print(f"  [DEBUG] Tool calls: {parsed.get('tool_calls', [])}")
                print(f"  [DEBUG] Response draft: {parsed.get('response', '')}")
                user_choice = input("\n[DEBUG] Press Enter to continue (or type 'exit')... ")
                if user_choice.strip().lower() == "exit":
                    return AgentOutput(status="aborted", response="[Engine] Aborted by developer in debug mode.")

            tool_calls = parsed.get("tool_calls", [])
            is_empty_turn = not tool_calls and not parsed.get("response", "")

            # Idle loop detection. Two independent signals feed the same counter:
            # (a) the classic "said the same decision/hypothesis text twice" check -- a weak
            #     signal, since minor LLM phrasing variance (e.g. after a JSON repair retry)
            #     can defeat exact string equality even when the agent is truly stuck;
            # (b) "produced neither a tool call nor a response" -- a strong signal, since a
            #     turn like that can never make progress on its own regardless of wording.
            current_thought = parsed.get("decision", "") + str(parsed.get("hypothesis", ""))
            if (current_thought == last_thought or is_empty_turn) and not tool_calls:
                same_thought_counter += 1
            else:
                same_thought_counter = 0
            last_thought = current_thought

            if same_thought_counter >= 2:
                print("  [Engine] Idle loop detected. Forcing Synthesis phase.")
                parsed["decision"] = "Forced Synthesis due to idle loop"
                tool_calls = []
                if not parsed.get("response"):
                    parsed["response"] = "I need user input to proceed, but I must summarize partial progress now."
            elif is_empty_turn:
                # Below the forced-synthesis threshold, but this turn produced nothing
                # actionable. Left alone, the next call would see an unchanged prompt (nothing
                # was appended to history) and would likely repeat the same non-answer
                # verbatim -- this was the root cause of a real ~30-iteration stall observed
                # against GigaChat on 2026-09-13 (see development_log.md).
                print("  [Engine] Empty turn (no tool_calls, no response). Nudging the agent to act.")
                await self.agent.add_to_history("assistant", json.dumps(parsed, ensure_ascii=False))
                await self.agent.add_to_history(
                    "user",
                    "[Engine] Your last reply contained neither a tool call nor a final 'response'. "
                    "You must do exactly one of: call a tool to gather more evidence, or set "
                    "'response' to your final answer now."
                )
                continue

            if tool_calls:
                observation_message, any_failed = await self._phase_collide(user_input, iteration, tool_calls, evidence_store)

                # Detect the agent repeating the exact same failing call instead of
                # changing strategy (observed on Cerebras/Groq with smaller models:
                # the agent kept retrying an identical failed tool call for 10+ turns).
                call_signature = json.dumps(tool_calls, sort_keys=True, ensure_ascii=False)
                if any_failed and call_signature == last_failed_call_signature:
                    repeated_failure_count += 1
                else:
                    repeated_failure_count = 0
                last_failed_call_signature = call_signature if any_failed else None

                if repeated_failure_count >= 1:
                    observation_message += (
                        "\n\n[Engine] You just repeated the exact same failing tool call. "
                        "Do not retry it verbatim. Either use a different tool/arguments to "
                        "recover (e.g. list/search before getting a specific item), or explain "
                        "in your final response why the task cannot proceed."
                    )

                await self.agent.add_to_history("assistant", json.dumps(parsed, ensure_ascii=False))
                await self.agent.add_to_history("user", f"Observation from tools:\n{observation_message}")
                continue

            response_text = parsed.get("response", "")
            if response_text:
                leap_type = parsed.get("leap_type", "")
                nothing_done_yet = len(evidence_store.all()) == 0

                if leap_type == "decompose_and_act" and nothing_done_yet and leap_mismatch_retries < 1:
                    # Second-order contradiction: the agent's OWN claim (leap_type='decompose_and_act')
                    # and its OWN actual development (evidence_store empty -- no tool has ever run in
                    # this task) have diverged. Rule 5 says a contradiction must be driven to a
                    # resolution, not just recorded -- so this is fed back into the SAME generative
                    # loop (bounded, like the idle-loop/repeated-failure nudges above) instead of being
                    # silently finalized with a passive flag. See development_log.md, 2026-09-13.
                    leap_mismatch_retries += 1
                    print("  [Engine] Contradiction: leap_type='decompose_and_act' but no tool has "
                          "ever been called in this task. Driving it back into development.")
                    await self.logger.trace_event("leap_action_mismatch", {
                        "session_id": user_input.session_id,
                        "iteration": iteration,
                        "reason": "leap_type='decompose_and_act' but no tool was ever called (caught before finalizing)",
                        "raw_response": json.dumps(parsed, ensure_ascii=False),
                        "provider_class": type(self.agent.llm).__name__,
                        "full_prompt": json.dumps(self.agent.get_messages(), ensure_ascii=False)[:8000],
                    })
                    await self.agent.add_to_history("assistant", json.dumps(parsed, ensure_ascii=False))
                    await self.agent.add_to_history(
                        "user",
                        "[Engine] Contradiction: you declared leap_type='decompose_and_act', claiming "
                        "you acted on the unambiguous part of the task, but no tool has been called yet "
                        "in this task at all. Your stated leap and your actual development have "
                        "diverged. Resolve this: (1) name which of your own earlier steps (hypothesis "
                        "or plan_steps) led you to conclude you could skip acting, then (2) either call "
                        "the tool that acts on the unambiguous part now, or honestly set leap_type to "
                        "'ask_only' with a reason nothing can be safely done yet."
                    )
                    continue

                agent_output = await self._phase_synthesize(user_input, iteration, parsed, evidence_store)
                
                # Phase 4 Validate
                validation_errors = await self._phase_validate(agent_output.claims, evidence_store, user_input.session_id)
                if validation_errors:
                    if validation_retries >= 1:
                        print(f"  [Validation] FAILED. Limit reached.")
                        agent_output.status = "validation_failed"
                        return agent_output
                        
                    validation_retries += 1
                    err_msg = "The following evidence IDs do not exist in the current run or are invalid:\n- " + "\n- ".join(validation_errors) + f"\n\nAvailable evidence IDs in current run:\n{evidence_store.ids()}\n\nRevise the claims using only existing evidence IDs. Do not invent new evidence IDs."
                    print(f"  [Validation] ERROR: {len(validation_errors)} discrepancies. Requesting correction...")
                    await self.agent.add_to_history("assistant", json.dumps(parsed, ensure_ascii=False))
                    await self.agent.add_to_history("user", err_msg)
                    await self.logger.trace_event("validation_failed", {
                        "session_id": user_input.session_id,
                        "iteration": iteration,
                        "errors": validation_errors,
                    })
                    continue

                print("  [Validation] Successfully passed.")
                agent_output.status = "completed"
                return agent_output

        await self.logger.trace_event("max_iterations_reached", {"iterations": self.max_iterations})
        return AgentOutput(
            status="max_iterations",
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
                
        result = await self.agent.llm.generate_result(self.agent.get_messages(), tools=tools_payload)
        
        if result.tool_calls:
            # Bypass parser for native tool calls
            parsed = {
                "decision": "Invoking native tools",
                "tool_calls": [{"name": tc.name, "args": tc.arguments} for tc in result.tool_calls]
            }
        else:
            try:
                parsed = parse_llm_response(result.text or "")
            except ParseError as e:
                print(f"  [!] Parsing error: {e}. Attempting controlled repair...")
                await self.logger.trace_event("parse_error_before_repair", {
                    "session_id": user_input.session_id,
                    "error": str(e),
                    "raw": str(result.text)[:200],
                })
                
                repairer = JsonRepairer(self.agent.llm)
                try:
                    parsed, repaired_result = await repairer.repair(str(result.text), e)
                    
                    # Accumulate usage
                    if result.usage and repaired_result.usage:
                        result.usage.prompt_tokens += repaired_result.usage.prompt_tokens
                        result.usage.completion_tokens += repaired_result.usage.completion_tokens
                        result.usage.total_tokens += repaired_result.usage.total_tokens
                    elif repaired_result.usage:
                        result.usage = repaired_result.usage
                        
                    print("  [+] Controlled repair successful.")
                    await self.logger.trace_event("repair_successful", {
                        "session_id": user_input.session_id
                    })
                except ControlledRepairError as repair_error:
                    print(f"  [!] Repair failed: {repair_error}")
                    await self.logger.trace_event("repair_failed", {
                        "session_id": user_input.session_id,
                        "error": str(repair_error),
                        "raw_after_repair": repair_error.raw_response[:200] if repair_error.raw_response else "",
                    })
                    raise  # Let the engine crash and bubble up the controlled error, as requested by the user.

        decision = parsed.get("decision", "")
        hyp_raw = parsed.get("hypothesis")
        
        if hyp_raw:
            print(f"  [Hypothesis] {hyp_raw.get('assumption', '')}")
            if hyp_raw.get("plan_steps"):
                print(f"  [Plan] " + ", ".join(hyp_raw.get("plan_steps", [])))

        print(f"  [Decision] {decision[:100]}")
        await self.logger.trace_event("generate", {
            "session_id": user_input.session_id,
            "iteration": iteration,
            "hypothesis": hyp_raw,
            "decision": decision,
            "tool_calls_count": len(parsed.get("tool_calls", [])),
            "has_response": bool(parsed.get("response")),
        })
        return parsed

    async def _phase_collide(self, user_input: AgentInput, iteration: int, tool_calls: list, evidence_store: EvidenceStore) -> tuple[str, bool]:
        observation_parts = []
        tool_tasks = []
        any_failed = False

        for call in tool_calls:
            import json
            tool_name = call.get("name", "")
            tool_args = call.get("args", {})
            
            action_hash = hash(json.dumps(tool_args, sort_keys=True))
            if (tool_name, action_hash) in evidence_store._executed_actions:
                obs = f"[Error] Action already successfully executed with these exact arguments"
                print(f"  [!] {obs}")
                observation_parts.append(obs)
                any_failed = True
                continue

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
                any_failed = True
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

                evidence_store.add(result)
                await self.logger.log_collision(
                    tool_name,
                    result.success,
                    str(result.content) if result.success else str(result.error),
                    session_id=user_input.session_id,
                )

                if result.success:
                    # Cap what gets injected into the conversation (and resent on every subsequent
                    # LLM call, growing each turn) -- the full content still lives in evidence_store.
                    # An uncapped tool result (e.g. a 16-apartment listing, ~7000+ chars) compounding
                    # over a few turns was observed pushing GigaChat past its effective context
                    # window, silently truncating its OUTPUT mid-JSON and causing a hard
                    # ControlledRepairError crash (see development_log.md, 2026-09-14).
                    content_str = str(result.content)
                    # 2026-09-14: 3000 was too aggressive -- it was observed cutting off a contacts
                    # listing before the specific Prague/40-48 matches the task needed, causing the
                    # agent to wrongly conclude "no matching contacts exist." Raised now that GigaChat's
                    # own max_tokens has more headroom (see adapter.py), leaving more room for a single
                    # observation to be seen whole while still bounding pathological cases.
                    max_obs_chars = 6000
                    if len(content_str) > max_obs_chars:
                        content_str = (
                            content_str[:max_obs_chars]
                            + f"\n... (truncated, {len(content_str) - max_obs_chars} more characters. "
                              f"Full result stored as Evidence ID {result.id} -- if this tool supports "
                              f"offset/limit or search/filter arguments, use them to narrow the result "
                              f"instead of requesting everything at once.)"
                        )
                    obs = f"[Evidence ID: {result.id} | Tool '{tool_name}'] Result:\n{content_str}"
                    import json
                    evidence_store._executed_actions.add((tool_name, hash(json.dumps(result.tool_calls_args if hasattr(result, 'tool_calls_args') else call.get("args", {}), sort_keys=True))))
                else:
                    obs = f"[Evidence ID: {result.id} | Tool '{tool_name}'] Error:\n{result.error}"
                    any_failed = True

                print(f"  [Observation] {obs}")
                observation_parts.append(obs)

        return "\n\n".join(observation_parts), any_failed

    async def _phase_synthesize(self, user_input: AgentInput, iteration: int, parsed: dict, evidence_store: EvidenceStore) -> AgentOutput:
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

        opposite_process = parsed.get("opposite_process", "")
        contradiction = parsed.get("contradiction", "")
        leap = parsed.get("leap", "")
        leap_type = parsed.get("leap_type", "")
        dialectical_resolution_missing = not (opposite_process and contradiction and leap)
        # True here means the leap_mismatch_retries bound in run() was exhausted and the engine
        # finalized anyway rather than looping forever -- still worth flagging for the auditor.
        leap_action_mismatch = leap_type == "decompose_and_act" and len(evidence_store.all()) == 0

        if dialectical_resolution_missing or leap_action_mismatch:
            reason = "opposite_process/contradiction/leap missing" if dialectical_resolution_missing \
                else "leap_type='decompose_and_act' but no tool was ever called"
            print(f"  [Engine] WARNING: finalized with a Rule 5 violation ({reason}) -- see dialectics_rules.md.")
            await self.logger.trace_event(
                "leap_action_mismatch" if leap_action_mismatch else "dialectical_resolution_missing",
                {
                    "session_id": user_input.session_id,
                    "iteration": iteration,
                    "reason": reason,
                    # Full forensic context (not a 200-char preview) so a later investigation
                    # (DialecticalAuditor.investigate_contradiction) can trace the contradiction
                    # back to its actual cause in the prompt, the provider, or the parsing code,
                    # instead of requiring a human to reproduce it by hand.
                    "raw_response": json.dumps(parsed, ensure_ascii=False),
                    "provider_class": type(self.agent.llm).__name__,
                    "full_prompt": json.dumps(self.agent.get_messages(), ensure_ascii=False)[:8000],
                },
            )

        return AgentOutput(
            response=response_text,
            decision=parsed.get("decision", ""),
            hypothesis=hypothesis,
            opposite_process=opposite_process,
            contradiction=contradiction,
            leap=leap,
            leap_type=leap_type,
            dialectical_resolution_missing=dialectical_resolution_missing,
            leap_action_mismatch=leap_action_mismatch,
            claims=claims,
            memory_updates=memory_updates,
            evidence=evidence_store.all(),
            is_final=True,
        )

    async def _phase_validate(self, claims: list[Claim], evidence_store: EvidenceStore, session_id: str) -> list[str]:
        validation_errors = []

        for claim in claims:
            for eid in claim.evidence_ids:
                if not evidence_store.exists(eid):
                    validation_errors.append(f"Claim '{claim.text}' refers to unknown evidence_id '{eid}'.")
            
            if claim.requires_validation and self.validator:
                val_err = await self.validator.validate(claim, evidence_store.all(), session_id=session_id)
                if val_err:
                    validation_errors.append(val_err)
                    
        return validation_errors
