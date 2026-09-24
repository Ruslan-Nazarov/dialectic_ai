import json
import asyncio
import re
from dataclasses import asdict
from jsonschema import Draft202012Validator
import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from dialectic_ai.core.logger import DevelopmentLogger
from dialectic_ai.core.runtime import (
    CommitLayer,
    DirectionSnapshot,
    Goal,
    MoveType,
    Proposal,
    RuntimeEvent,
    RuntimeState,
)
from dialectic_ai.core.domain import Domain
from dialectic_ai.core.schema import AgentInput
from dialectic_ai.core.semantic_validator import SemanticValidator, LLMSemanticValidator, FakeSemanticValidator
from dialectic_ai.core.llm import MockLLM
from dialectic_ai.core.proposal_schema import proposal_schema
from dialectic_ai.engine.prompt import build_v2_prompt, apply_aliases


class RuntimeResult(BaseModel):
    status: str
    response: str
    run_id: str
    completion_id: Optional[str] = None
    stop_reason: Optional[str] = None
    validation_mode: str = "semantic"
    roadmap_id: Optional[str] = None


def _schema_error(errors) -> str:
    """Names the failing field and the rule it broke. A bare jsonschema message for an anyOf
    ("{...} is not valid under any of the given schemas") names neither, and the model kept
    resubmitting the same invalid field until the rejection budget ran out."""
    from jsonschema.exceptions import best_match
    error = best_match(errors)
    path = ".".join(str(p) for p in error.absolute_path) or "(root)"
    message = f"at {path}: {error.message}"
    # Where the schema says how to satisfy the rule, pass that on: naming the broken rule alone
    # was not enough -- the model resubmitted the same ungrounded field eight times running.
    hint = error.schema.get("description") if isinstance(error.schema, dict) else None
    return f"{message}. Hint: {hint}" if hint else message


def _resolve_payload_aliases(payload, alias_to_uuid: dict):
    """Translates graph aliases (P1, C2, A1, ...) back to UUIDs everywhere except tool arguments.
    Tool arguments are the tool's own data, not graph references: a tool may use ids of its own
    that look like aliases (the business-card answers are A1, A2, ... -- the same labels as
    actions), and rewriting them sent the tool a UUID it had never issued."""
    if not isinstance(payload, dict) or "args" not in payload:
        return apply_aliases(payload, alias_to_uuid)
    tool_args = payload["args"]
    resolved = apply_aliases({k: v for k, v in payload.items() if k != "args"}, alias_to_uuid)
    resolved["args"] = tool_args
    return resolved


class DialecticalEngine:
    def __init__(
        self,
        agent,
        logger: Optional[DevelopmentLogger] = None,
        max_iterations: int = 30,
        # 5 was too tight: the anti-repeat STOP-nudges (see the "STOP." block below) only kick in
        # after 2 identical-move rejections and then need a further attempt or two to actually
        # take effect once they do -- observed live, a run that eventually self-corrected and
        # completed correctly needed its 5th attempt at the same move to succeed, while an
        # otherwise-identical run died at exactly 5 one step short. 8 gives the self-correction
        # mechanism the room it needs to work as designed, without being unbounded.
        max_rejected_proposals: int = 8,
        # Judge outages (no verdict at all) are budgeted separately: they say nothing about the
        # proposal, and on the business-card pilot they consumed half of the rejection budget.
        max_judge_outages: int = 6,
        semantic_validator: Optional[SemanticValidator] = None,
        model_timeout: float = 90,
        tool_timeout: float = 30,
        run_timeout: float = 300,
        domain: Optional[Domain] = None,
    ):
        self.agent = agent
        self.logger = logger or DevelopmentLogger()
        self.max_iterations = max_iterations
        self.max_rejected_proposals = max_rejected_proposals
        self.max_judge_outages = max_judge_outages
        self.semantic_validator = semantic_validator
        self.model_timeout = model_timeout
        self.tool_timeout = tool_timeout
        self.run_timeout = run_timeout
        self.domain = domain
        self._running = False
        self.validation_mode = "semantic"
        self._last_move_type_requested = None
        self._repeat_invalid_move_count = 0
        self._planning_stagnation_count = 0

        # Tool registry: name -> Tool
        self._tool_registry = {t.name: t for t in getattr(agent, "tools", [])}

        self.state = RuntimeState()
        self.commit_layer = CommitLayer()
        self.run_id = str(uuid.uuid4())

        # For parsing if text provider is used
        from dialectic_ai.engine.repair import JSONRepairer
        self.repairer = JSONRepairer(self.agent)

    async def run(self, user_input: AgentInput) -> RuntimeResult:
        if self._running:
            raise RuntimeError("Concurrent runs require separate engine instances")
        self._running = True
        self.state = RuntimeState()
        self.run_id = str(uuid.uuid4())
        try:
            try:
                return await asyncio.wait_for(self._run(user_input), self.run_timeout)
            except asyncio.TimeoutError:
                return await self._failure("run_timeout", "Run deadline reached; unfinished roadmap preserved")
        finally:
            self._running = False

    async def _run(self, user_input: AgentInput) -> RuntimeResult:
        validator = self.semantic_validator
        if validator is None:
            validator, self.validation_mode = self._build_default_semantic_validator()
        else:
            self.validation_mode = "simulation" if isinstance(validator, FakeSemanticValidator) else "semantic"
        if isinstance(validator, LLMSemanticValidator):
            validator.agent_goal = getattr(self.agent, "goal", "")
            validator.domain = self.domain
        semantic_validator = validator
        # 1. Start V2 Run
        goal = Goal(content=user_input.user_message)
        self.state._goals[goal.id] = goal

        rejected_count = 0
        judge_outages = 0
        iteration = 0
        self._last_move_type_requested = None
        self._repeat_invalid_move_count = 0
        self._planning_stagnation_count = 0
        await self.logger.trace_event("run_started", {"run_id": self.run_id, "goal": asdict(goal), "validation_mode": self.validation_mode})
        
        while iteration < self.max_iterations:
            iteration += 1
            
            # 2. Get Allowed Moves & Direction
            from dialectic_ai.core.runtime import AllowedMovesResolver
            resolver = AllowedMovesResolver()
            allowed_moves = resolver.allowed_moves(self.state)
            if self.domain and self.domain.opposite:
                if await self._designate_domain_opposite(allowed_moves):
                    continue
                allowed_moves = [m for m in allowed_moves if m != MoveType.DESIGNATE_OPPOSITE]
            await self.logger.trace_event("allowed_moves", {"run_id": self.run_id, "iteration": iteration,
                                                              "moves": [m.name for m in allowed_moves],
                                                              "phase": self.state.phase})

            active_frontier = [p.id for p in self.state.get_all_processes() if self.state.is_committed(p.id)]
            direction = DirectionSnapshot(
                goal_id=goal.id,
                active_frontier_process_ids=active_frontier,
                pending_action_ids=[],
                active_contradiction_ids=[c.id for c in self.state.get_all_contradictions()]
            )
            
            # Build Context
            # For simplicity, getting just names of allowed moves
            allowed_moves_names = [m.name for m in allowed_moves]
            
            # 3. Prompt LLM for ONE Proposal
            prompt, alias_to_uuid = build_v2_prompt(
                self.state, goal, allowed_moves_names,
                iteration=iteration, max_iterations=self.max_iterations,
                agent_goal=self._actor_role(), tools=list(self._tool_registry.values()),
                include_runtime_json=getattr(self.agent.llm, "reads_runtime_json", False),
            )

            # A model can lock onto a move that is not legal now (e.g. reaching for
            # PROPOSE_ACTION while still in the design phase) and repeat it verbatim
            # across retries, even though the prompt lists only allowed moves. When
            # that repetition is detected, put the correction where it can't be
            # missed: first, in its own sentence, before anything else.
            if (
                self._repeat_invalid_move_count >= 2
                and self._last_move_type_requested is not None
                and self._last_move_type_requested not in allowed_moves_names
            ):
                prompt = (
                    f"STOP. Your last {self._repeat_invalid_move_count} responses all proposed "
                    f"move_type = \"{self._last_move_type_requested}\", and every one was rejected because "
                    f"that move is not currently allowed. You MUST propose a DIFFERENT move_type this time, "
                    f"chosen from exactly this list: {allowed_moves_names}. Do not repeat "
                    f"\"{self._last_move_type_requested}\" again.\n\n"
                ) + prompt

            # A model can keep committing legal but LATERAL moves -- developing further,
            # or re-designating a brand new opposite instead of using the one it already has --
            # forever without ever spending a turn on the move that actually advances the
            # protocol (ESTABLISH_CONTRADICTION, PROPOSE_LEAP, BEGIN_EXECUTION), even once that
            # move is allowed. Each individual lateral move is valid on its own, so the
            # anti-repeat detector above (which only fires on repeated REJECTED moves) never
            # sees this as a problem. Observed live with GigaChat on a trivial arithmetic task,
            # twice: first 11x DEVELOP_PROCESS never reaching DESIGNATE_OPPOSITE, then -- after
            # that was fixed -- 5x DESIGNATE_OPPOSITE (a fresh opposite each time) never reaching
            # ESTABLISH_CONTRADICTION. Name the stagnation explicitly once it recurs, pointing at
            # whichever advancing move is currently the furthest reachable.
            _ADVANCING_MOVES_PRIORITY = ["BEGIN_EXECUTION", "PROPOSE_LEAP", "ESTABLISH_CONTRADICTION"]
            advancing_target = next((m for m in _ADVANCING_MOVES_PRIORITY if m in allowed_moves_names), None)
            if self._planning_stagnation_count >= 2 and advancing_target:
                prompt = (
                    f"NOTE: your last {self._planning_stagnation_count} proposals developed the world further or "
                    f"created new designations without ever committing to {advancing_target}, even though "
                    f"{advancing_target} is now allowed with what you already have committed. Do not create another "
                    f"process, development, or opposite designation this turn. Propose {advancing_target} now, "
                    f"reusing already-committed entities, unless you have a specific reason it cannot yet be "
                    f"satisfied (state that reason explicitly in why_this_move_now).\n\n"
                ) + prompt

            # Some moves can be legal and still get rejected repeatedly for the SAME kind of
            # semantic mistake, worded slightly differently each time -- _repeat_invalid_move_count
            # already tracks "same requested move_type N times in a row" regardless of accept/reject,
            # so reuse it here instead of per-move counters. Observed live: 5 consecutive PROPOSE_LEAP
            # rejections, each a reworded restatement of the contradiction's own unity_justification;
            # separately, 5 consecutive DESIGNATE_OPPOSITE rejections oscillating between "the leap
            # already happened" (too concrete/realized) and a bare negation (not a state at all) --
            # neither ever landing on the actual required shape. Each burns max_rejected_proposals
            # with zero progress unless corrected explicitly, by name, after the pattern repeats.
            _SEMANTIC_REPEAT_HINTS = {
                "PROPOSE_LEAP": (
                    "Your last {n} PROPOSE_LEAP attempts were rejected as vague restatements of the "
                    "contradiction's own unity_justification (\"combine/integrate both processes\"), not as a "
                    "genuinely new concrete process. Before proposing again, answer concretely: what specific "
                    "sequence of steps IS the leap -- name it the way you would name a committed_process's "
                    "content field, not the way you'd describe why a leap is needed. If you cannot state one "
                    "concretely yet, reconsider whether ESTABLISH_CONTRADICTION was premature instead of forcing "
                    "another vague leap."
                ),
                "DESIGNATE_OPPOSITE": (
                    "Your last {n} DESIGNATE_OPPOSITE attempts were rejected. You are likely stuck in one of three "
                    "wrong shapes: (a) a competing technique that still serves the SAME need as the simplest -- an "
                    "alternative check, estimate, or verification method still aimed at the same target (this "
                    "shares the simplest's need and is NOT independent, no matter how different it looks "
                    "mechanically); (b) a fully realized/concrete resolution -- something that already happened; "
                    "or (c) a bare negation of the simplest (\"X does NOT hold\"). None of these is a valid "
                    "opposite. What is required is a process/state serving a GENUINELY DIFFERENT need -- one whose "
                    "own development does not depend on the simplest ever having run at all. State explicitly, in "
                    "one sentence, what need the simplest serves and what DIFFERENT need your proposed opposite "
                    "serves -- if you cannot name a different need, you have not found a real opposite yet."
                ),
                "BEGIN_EXECUTION": (
                    "Your last {n} BEGIN_EXECUTION attempts were rejected as \"not a real revision\" -- you are "
                    "resubmitting a roadmap whose resolution_ids/execution_process_ids are IDENTICAL to one that "
                    "was already tried and already contradicted by practice. Reusing the same failed leap will be "
                    "rejected every time, no matter how many times you retry it verbatim. You MUST propose a "
                    "genuinely NEW PROPOSE_LEAP first -- one that specifically accounts for why the previous "
                    "attempt(s) failed -- and only then call BEGIN_EXECUTION with that new resolution's ID. Do "
                    "not call BEGIN_EXECUTION again until you have done that."
                ),
                "ASSESS_PRACTICE": (
                    "Your last {n} ASSESS_PRACTICE attempts were rejected for marking expected_actual_relation as "
                    "'confirmed' (or similar) when the observation's raw_result does NOT match the action's own "
                    "expectation. This field compares raw_result to expectation ONLY -- it is not about whether "
                    "your explanation is well-written. If the numbers/values differ at all, the correct value is "
                    "'contradicted', full stop, regardless of how confident your explanation sounds. Re-read the "
                    "observation's actual raw_result and the action's expectation field again before answering."
                ),
            }
            hint = _SEMANTIC_REPEAT_HINTS.get(self._last_move_type_requested)
            if (
                self._repeat_invalid_move_count >= 2
                and hint
                and self._last_move_type_requested in allowed_moves_names
            ):
                prompt = (
                    f"STOP. " + hint.format(n=self._repeat_invalid_move_count) + "\n\n"
                ) + prompt

            tools_payload = []
            if getattr(self.agent, "tool_calling_mode", "") == "native":
                tools_payload = [{
                    "type": "function",
                    "function": {
                        "name": "submit_proposal",
                        "description": "Submit exactly ONE dialectical proposal. For PROPOSE_ACTION, include 'tool_name' and 'args' in payload.",
                        "parameters": proposal_schema(allowed_moves_names)
                    }
                }]
                try:
                    result = await asyncio.wait_for(self.agent.llm.generate_result([{"role": "user", "content": prompt}], tools=tools_payload), self.model_timeout)
                    proposal_data = self._parse_native_proposal(result)
                except Exception as exc:
                    return await self._failure("provider_error", f"Model request failed: {type(exc).__name__}: {exc}")
            else:
                text_prompt = prompt + (
                    "\n\nRespond with exactly ONE JSON object, and nothing else. "
                    f'"move_type" MUST be exactly one of these strings: {allowed_moves_names}. '
                    "Any other move_type will be rejected.\n"
                    "{\n"
                    f'  "move_type": "<pick exactly one from {allowed_moves_names}>",\n'
                    '  "payload": { ... fields required by that move ... },\n'
                    '  "why_this_move_now": "short reason",\n'
                    '  "expected_goal_contribution": "short reason"\n'
                    "}\n"
                )
                try:
                    result = await asyncio.wait_for(self.agent.llm.generate([{"role": "user", "content": text_prompt}]), self.model_timeout)
                    proposal_data = await self._parse_text_proposal(result)
                except Exception as exc:
                    return await self._failure("provider_error", f"Model request failed: {type(exc).__name__}: {exc}")
                
            # The model was shown short aliases (P1, C2, ...), not real UUIDs, to avoid the
            # transcription/hallucination failures long IDs invite (see build_alias_map). Translate
            # any alias it used back to the real UUID before schema/structural validation ever sees
            # the payload -- everything downstream of this point still speaks real UUIDs.
            if isinstance(proposal_data, dict) and isinstance(proposal_data.get("payload"), (dict, list)):
                proposal_data["payload"] = _resolve_payload_aliases(proposal_data["payload"], alias_to_uuid)

            requested_move = proposal_data.get("move_type") if isinstance(proposal_data, dict) else None
            if requested_move == self._last_move_type_requested:
                self._repeat_invalid_move_count += 1
            else:
                self._last_move_type_requested = requested_move
                self._repeat_invalid_move_count = 1

            errors = list(Draft202012Validator(proposal_schema(allowed_moves_names)).iter_errors(proposal_data))
            if errors:
                await self._reject("Proposal schema: " + _schema_error(errors))
                rejected_count += 1
                if rejected_count >= self.max_rejected_proposals:
                    return await self._failure("max_rejected_proposals", "Too many rejected proposals")
                continue
            move_type_enum = MoveType(proposal_data["move_type"])

            proposal = Proposal(
                move_type=move_type_enum,
                payload=proposal_data.get("payload", {}),
                why_this_move_now=proposal_data.get("why_this_move_now", ""),
                expected_goal_contribution=proposal_data.get("expected_goal_contribution", "")
            )
            
            # 4. Structural Validation
            from dialectic_ai.core.runtime import StructuralValidator
            validator = StructuralValidator()
            is_struct_valid, struct_err = validator.validate(proposal, self.state)
            if not is_struct_valid:
                await self._reject(f"Structural: {struct_err}", proposal)
                rejected_count += 1
                if rejected_count >= self.max_rejected_proposals:
                    return await self._failure("max_rejected_proposals", "Too many rejected proposals")
                continue
                
            # 5. Semantic Validation (where required)
            unjudged = self.domain is not None and move_type_enum in self.domain.unjudged_moves
            if semantic_validator and not unjudged:
                try:
                    # Judge a detached view; a validator must not mutate committed runtime state.
                    import copy
                    sem_res = await asyncio.wait_for(semantic_validator.validate(copy.deepcopy(proposal), copy.deepcopy(self.state), copy.deepcopy(goal)), self.model_timeout)
                except Exception as exc:
                    await self._reject(f"Semantic validator failed: {type(exc).__name__}: {exc}", proposal)
                    rejected_count += 1
                    if rejected_count >= self.max_rejected_proposals:
                        return await self._failure("max_rejected_proposals", "Too many rejected proposals")
                    continue
                if not sem_res.accepted and getattr(sem_res, "unavailable", False):
                    # Not a verdict: tell the actor to resubmit unchanged, and keep the raw provider
                    # error out of its feedback so it does not try to "fix" a non-problem.
                    await self._reject("Judge unavailable (no verdict was returned); resubmit the same "
                                       "proposal unchanged.", proposal, cause=sem_res.reason)
                    judge_outages += 1
                    if judge_outages >= self.max_judge_outages:
                        return await self._failure("judge_unavailable", f"Judge returned no verdict {judge_outages} times: {sem_res.reason}")
                    continue
                if not sem_res.accepted:
                    await self._reject(f"Semantic: {sem_res.reason}", proposal)
                    rejected_count += 1
                    if rejected_count >= self.max_rejected_proposals:
                        return await self._failure("max_rejected_proposals", "Too many rejected proposals")
                    continue
            
            if move_type_enum == MoveType.PROPOSE_ACTION:
                tool = self._tool_registry.get(proposal.payload["tool_name"])
                if tool is None:
                    await self._reject("Unknown tool: " + proposal.payload["tool_name"], proposal)
                    rejected_count += 1
                    if rejected_count >= self.max_rejected_proposals:
                        return await self._failure("max_rejected_proposals", "Too many rejected proposals")
                    continue
                schema = tool.parameters()
                errors = list(Draft202012Validator(schema).iter_errors(proposal.payload["args"]))
                if errors:
                    await self._reject("Tool arguments: " + _schema_error(errors), proposal)
                    rejected_count += 1
                    if rejected_count >= self.max_rejected_proposals:
                        return await self._failure("max_rejected_proposals", "Too many rejected proposals")
                    continue

            # 6. Commit
            try:
                result_id = self.commit_layer.commit(proposal, self.state)
                rejected_count = 0 # Reset count on successful commit
                if move_type_enum in (
                    MoveType.DEVELOP_PROCESS, MoveType.CONNECT_DEVELOPMENT,
                    MoveType.DESIGNATE_OPPOSITE, MoveType.ASSESS_SIMPLEST,
                ):
                    self._planning_stagnation_count += 1
                else:
                    self._planning_stagnation_count = 0
            except ValueError as exc:
                await self._reject(str(exc), proposal)
                rejected_count += 1
                if rejected_count >= self.max_rejected_proposals:
                    return await self._failure("max_rejected_proposals", "Too many rejected proposals")
                continue
            await self.logger.trace_event("proposal_committed", {"run_id": self.run_id, "proposal": asdict(proposal), "result_id": result_id})
                
            if move_type_enum == MoveType.BEGIN_EXECUTION:
                await self.logger.trace_event("roadmap_accepted", {"run_id": self.run_id, "roadmap": asdict(self.state._roadmaps[result_id])})

            # 7. Action Execution (if PROPOSE_ACTION was committed)
            if move_type_enum == MoveType.PROPOSE_ACTION:
                action = self.state.get_action(result_id)
                if action and action.tool_name in self._tool_registry:
                    tool = self._tool_registry[action.tool_name]
                    try:
                        tool_result = await asyncio.wait_for(tool.execute(action.args), self.tool_timeout)
                        self.commit_layer.create_observation(
                            state=self.state,
                            action_id=action.id,
                            raw_result=tool_result.content,
                            success=getattr(tool_result, 'success', True),
                            error=getattr(tool_result, 'error', None) if not getattr(tool_result, 'success', True) else None
                        )
                    except Exception as e:
                        self.commit_layer.create_observation(self.state, action.id, str(e), False, str(e))
                else:
                    self.commit_layer.create_observation(self.state, action.id, "Tool not found", False, "Tool not found")
                    
                observation = self.state.get_all_observations()[-1]
                await self.logger.trace_event("observation", {"run_id": self.run_id, "observation": asdict(observation)})

            # 8. Completion Check
            if move_type_enum == MoveType.REPORT_CONTRADICTION:
                # An honest end, not a success: callers must be able to tell "the answer" from
                # "what independent evidence supports, given a source that kept contradicting it".
                report = self.state._unresolved_reports[result_id]
                await self.logger.trace_event("run_finished", {"run_id": self.run_id, "status": "unresolved",
                                                               "report": asdict(report)})
                return RuntimeResult(status="unresolved", response=report.final_response, run_id=self.run_id,
                                     stop_reason="unresolved_contradiction", validation_mode=self.validation_mode,
                                     roadmap_id=self.state.active_roadmap_id)
            if move_type_enum == MoveType.COMPLETE:
                completion = self.state._completions[result_id]
                await self.logger.trace_event("run_finished", {"run_id": self.run_id, "status": "completed", "completion": asdict(completion)})
                return RuntimeResult(
                    status="completed",
                    response=completion.final_response,
                    run_id=self.run_id,
                    completion_id=result_id,
                    validation_mode=self.validation_mode,
                    roadmap_id=self.state.active_roadmap_id
                )

        return await self._failure("max_iterations", "Max iterations reached; unfinished structure preserved")

    def _actor_role(self) -> str:
        role = getattr(self.agent, "goal", "")
        if self.domain:
            role += f"\n\nDomain meaning of the dialectical terms ({self.domain.name}):\n{self.domain.semantics}"
        return role

    async def _designate_domain_opposite(self, allowed_moves) -> bool:
        """Commits the domain's fixed opposite as soon as it becomes designatable. The
        model develops it afterwards but never chooses it, and the judge never re-argues
        it. Returns True when a designation was committed this iteration."""
        from dialectic_ai.core.runtime import DesignationRole
        if MoveType.DESIGNATE_OPPOSITE not in allowed_moves:
            return False
        designations = self.state.get_all_designations()
        if any(d.role == DesignationRole.OPPOSITE for d in designations):
            return False
        simplest = next((d for d in designations if d.role == DesignationRole.SIMPLEST), None)
        developed = [r for r in self.state.get_all_development_relations()
                     if simplest and self.state.is_committed(r.id)
                     and r.source_process_id == simplest.process_id]
        if not developed:
            return False
        proposal = Proposal(
            move_type=MoveType.DESIGNATE_OPPOSITE,
            payload={"simplest_id": simplest.id, "context_id": developed[-1].emergent_process_id,
                     "content": self.domain.opposite, "justification": self.domain.opposite_justification},
            why_this_move_now="The domain fixes this opposite in advance.",
            expected_goal_contribution="Lets the model develop the opposite the domain defines.",
        )
        result_id = self.commit_layer.commit(proposal, self.state)
        await self.logger.trace_event("proposal_committed", {"run_id": self.run_id, "proposal": asdict(proposal),
                                                             "result_id": result_id, "origin": "domain"})
        return True

    async def _reject(self, reason, proposal=None, cause=None):
        """`reason` is what the actor sees next; `cause`, when given, is the underlying error kept
        only in the trace -- e.g. the provider error behind a judge outage."""
        event = RuntimeEvent(event_type="proposal_rejected", proposal=proposal, validation_error=reason)
        self.state._trace.append(event)
        record = {"run_id": self.run_id, "reason": reason, "proposal": asdict(proposal) if proposal else None}
        if cause:
            record["cause"] = cause
        await self.logger.trace_event("proposal_rejected", record)

    async def _failure(self, reason, response):
        await self.logger.trace_event("run_finished", {"run_id": self.run_id, "status": "error", "stop_reason": reason})
        return RuntimeResult(status="error", response=response, run_id=self.run_id, stop_reason=reason, validation_mode=self.validation_mode, roadmap_id=self.state.active_roadmap_id)

    def _build_default_semantic_validator(self):
        """
        Picks a semantic judge for this run when the caller didn't supply one.

        A model judging its own proposals is a broken judge: it inherits the
        same biases and blind spots as the proposer, which in practice means
        near-certain self-rejection loops (confirmed with GigaChat judging
        GigaChat -- every PROPOSE_SIMPLEST was rejected as "lacking a
        defensible relationship to the task", exhausting max_rejected_proposals
        before a single move ever committed). So: prefer a distinct, already
        configured provider as judge. Only fall back to self-judgment when no
        other real provider is available -- that preserves old single-provider
        behavior instead of silently disabling semantic checking.
        """
        if isinstance(self.agent.llm, MockLLM):
            return FakeSemanticValidator(), "simulation"

        from dialectic_ai.core.llm import FallbackLLM
        from dialectic_ai.integrations.providers import available_providers, build_llm

        # FallbackLLM takes the first candidate that answers WITHOUT throwing --
        # it never compares answers across providers, so a bad-but-confident judge
        # is just as sticky as a good one. A point-test (one good and one bad
        # hand-written DESIGNATE_OPPOSITE proposal, judged by each provider
        # individually) found Groq (llama/gpt-oss on Groq's endpoint) confidently
        # WRONG on the good case -- it false-rejected a genuinely independent
        # opposite -- while Gemini and Cerebras got all three cases right. Until
        # re-tested and shown reliable, Groq is excluded from judging entirely
        # (it remains usable as an actor provider).
        #
        # Gemini is kept in the pool (it can still judge correctly) but pushed to the
        # back of the priority order, not excluded outright: its free tier caps at 20
        # requests/DAY, and a single dialectical run can need a dozen+ semantic-judge
        # calls, so putting it first burns the day's quota on 429s before ever reaching
        # a usable judge -- observed live: a full run timed out because every judge call
        # tried and failed against Gemini first. Cerebras, confirmed reliable above,
        # goes first instead.
        JUDGE_EXCLUDED_PROVIDERS = {"groq"}
        judge_priority = {"cerebras": 0, "openai": 1, "gigachat": 2, "gemini": 3, "openrouter": 4}
        actor_provider = getattr(self.agent.llm, "provider_name", None)
        judge_candidates = []
        judge_pool = [n for n in available_providers() if n not in JUDGE_EXCLUDED_PROVIDERS]
        for name in sorted(judge_pool, key=lambda n: judge_priority.get(n, 99)):
            if name == actor_provider:
                continue
            try:
                candidate = build_llm(name)
            except Exception:
                continue
            # A judge candidate that is out of quota or unreachable should not
            # burn its own retry-with-backoff budget before FallbackLLM moves
            # on to the next one -- that turns "fail over fast" into "wait
            # ~10s per dead provider, per iteration".
            if hasattr(candidate, "max_retries"):
                candidate.max_retries = 1
            judge_candidates.append(candidate)

        if len(judge_candidates) == 1:
            return LLMSemanticValidator(judge_candidates[0]), "semantic"
        if judge_candidates:
            # Several distinct providers configured: chain them so one provider's
            # quota/outage doesn't sink the whole run's semantic validation.
            return LLMSemanticValidator(FallbackLLM(judge_candidates)), "semantic"

        return LLMSemanticValidator(self.agent.llm), "semantic_self_judged"

    def _parse_native_proposal(self, result) -> Optional[Dict[str, Any]]:
        if len(result.tool_calls) != 1:
            return None
        tc = result.tool_calls[0]
        if tc.name != "submit_proposal":
            return None
        return tc.arguments

    async def _parse_text_proposal(self, text: str) -> Optional[Dict[str, Any]]:
        if not isinstance(text, str):
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Cheap, local recovery for the common "wrapped the JSON in a Markdown
        # fence anyway" case, before paying for a full repair round-trip.
        fenced = re.fullmatch(r"\s*```(?:json)?[ \t]*\r?\n(.*?)\r?\n```\s*", text, re.DOTALL | re.IGNORECASE)
        if fenced:
            try:
                return json.loads(fenced.group(1))
            except json.JSONDecodeError:
                pass
        if self.repairer:
            try:
                repaired_text = await asyncio.wait_for(self.repairer.repair(text), self.model_timeout)
                return json.loads(repaired_text)
            except Exception:
                pass
        return None

