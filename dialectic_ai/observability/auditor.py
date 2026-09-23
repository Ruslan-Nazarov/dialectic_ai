"""
dialectic_ai/observability/auditor.py

DIALECTICAL DESCRIPTION:
  Origin: AgentEvaluator evaluates the agent's session post-factum based on traces.
    But a trace is post-factum. There is no mechanism that asks during development: 
    "Are we moving in the right direction? Are we following the methodology?"
  Contradiction: A developer can write excellent code while systematically violating
    dialectical principles — not documenting alternatives, not verifying steps through execution.
    AgentEvaluator does not see this.
  How it resolves: DialecticalAuditor collects the full context (dialectical map, development log,
    agent config, trace) and sends it to LLM with an auditing prompt. Two independent analyses: 
    PRODUCT (agent architecture) + PROCESS (how it was developed).
  What it leads to: CLI command `dialectic audit`. A quantitative report on violations
    of methodology before accumulating technical debt. An automatic reminder
    after N iterations of the agent.
  Its own contradictions: The quality of the audit depends on LLM and the completeness of the context.
    An empty development_log gives a blind audit. LLM may agree instead of criticizing.

  Relationship to AgentEvaluator (`dialectic eval`, observability/evaluator.py): that class
  is the fast, local, heuristic sibling -- no LLM call, pure trace-counting (including a
  rule5_violations count). This class is the slower, LLM-as-judge sibling -- deeper
  product+process compliance review, plus investigate_contradiction() for a root-cause
  hypothesis on one specific contradiction event. Run the evaluator first/often; reach for
  this one when you need a judgment call trace-counting alone can't make.
"""
import json
from pathlib import Path
from typing import Optional

from dialectic_ai.core.dialectical import dialectical, get_dialectical_map

AUDIT_PROMPT_PATH = Path(__file__).parent / "audit_prompt.md"
DEFAULT_METHODOLOGY_PATH = Path(__file__).parent.parent.parent / "dialectics_rules.md"
DEFAULT_LOG_PATH = Path(__file__).parent.parent.parent / "development_log.md"

# Framework source relative to the project root that always participates in producing a turn's
# JSON response -- read by investigate_contradiction() as the standing suspects for any
# contradiction, regardless of which provider was used.
_CORE_CHAIN_FILES = [
    "dialectic_ai/engine/executor.py",
    "dialectic_ai/engine/repair.py",
    "dialectic_ai/engine/parser.py",
    "dialectic_ai/agent/prompt_builder.py",
]
# Provider-specific file, added on top of the core chain when the trace event names the class.
_PROVIDER_FILE_MAP = {
    "GigaChatLLM": "dialectic_ai/integrations/gigachat/llm.py",
    "OpenAILLM": "dialectic_ai/integrations/openai/llm.py",
    "GeminiLLM": "dialectic_ai/integrations/gemini/llm.py",
    "BalancingLLM": "dialectic_ai/core/llm.py",
    "FallbackLLM": "dialectic_ai/core/llm.py",
    "MockLLM": "dialectic_ai/core/llm.py",
}
_CONTRADICTION_EVENT_TYPES = ("dialectical_resolution_missing", "leap_action_mismatch")


@dialectical(
    origin="AgentEvaluator evaluates post-factum. There is no reflection tool during development.",
    contradiction="A developer can systematically violate the methodology — AgentEvaluator sees only "
                  "traces, not the decisions and the process of making them.",
    resolves="Collects the full context (dialectical map, development log, agent config) "
             "and sends it to LLM with an auditing prompt. Two analyses: product + process.",
    generates="CLI command `dialectic audit`. A quantitative report on violations of methodology. "
              "An automatic reminder after N iterations of the agent.",
    own_contradictions="The quality of the audit depends on LLM and the completeness of the context. "
                       "An empty development_log = blind audit. LLM may agree instead of criticizing.",
    layer=5,
)
class DialecticalAuditor:
    """
    Meta-level reflection: checks the compliance of the agent's architecture
    and the process of its development with dialectical methodology.

    Two modes:
      - audit_agent(config_path, trace_path): audit of a specific agent
      - audit_framework(): audit of the framework itself (dialectical map + log)

    Example:
        from dialectic_ai.integrations.gemini.llm import GeminiLLM
        auditor = DialecticalAuditor(llm=GeminiLLM())
        report = await auditor.audit_agent("myagent.json")
        print(report)
    """

    def __init__(
        self,
        llm=None,
        prompt_path: Optional[Path] = None,
        methodology_path: Optional[Path] = None,
        run_reminder_after_iterations: int = 5,
    ):
        """
        Args:
            llm: Any BaseLLM. If not provided — only context collection without LLM analysis.
            prompt_path: Path to the prompt template (default: audit_prompt.md next to the module).
            methodology_path: Path to the rules (default: dialectics_rules.md at the project root).
            run_reminder_after_iterations: After how many iterations of the agent to remind about the audit.
        """
        self.llm = llm
        self.prompt_path = prompt_path or AUDIT_PROMPT_PATH
        self.methodology_path = methodology_path or DEFAULT_METHODOLOGY_PATH
        self.run_reminder_after_iterations = run_reminder_after_iterations
        self._iterations_since_audit = 0

    # ─── Public API ────────────────────────────────────────────────────────

    async def audit_agent(
        self,
        config_path: Optional[str] = None,
        trace_path: Optional[str] = "trace.jsonl",
        log_path: Optional[str] = None,
    ) -> str:
        """
        Audit of a specific agent in development.

        Collects: JSON config of the agent, trace of the last sessions,
        development log, @dialectical map.

        Returns:
            Text of the audit report from LLM.
        """
        context_parts = []

        # 1. Agent config
        if config_path and Path(config_path).exists():
            try:
                config_text = Path(config_path).read_text(encoding="utf-8")
                context_parts.append(
                    f"### Agent Configuration ({config_path}):\n```json\n{config_text}\n```"
                )
            except Exception:
                pass

        # 2. Trace (last 30 events)
        if trace_path and Path(trace_path).exists():
            try:
                lines = Path(trace_path).read_text(encoding="utf-8").strip().splitlines()
                recent = lines[-30:]
                context_parts.append(
                    f"### Trace of the last sessions (last {len(recent)} events from {trace_path}):\n"
                    + "\n".join(recent)
                )
            except Exception:
                pass

        # 3. Development log
        log_context = self._read_log(log_path or str(DEFAULT_LOG_PATH))
        if log_context:
            context_parts.append(f"### Development Log (development_log.md):\n{log_context}")
        else:
            context_parts.append("### Development Log: MISSING OR EMPTY")

        # 4. @dialectical map
        dialectical_map = self._collect_dialectical_map()
        if dialectical_map:
            context_parts.append(
                f"### Registered @dialectical components:\n{dialectical_map}"
            )

        context = "\n\n".join(context_parts)
        audit_mode = f"AUDIT AGENT — {config_path or 'without config'}"

        self._iterations_since_audit = 0
        return await self._run_audit(audit_mode, context)

    async def audit_framework(self, log_path: Optional[str] = None) -> str:
        """
        Audit of the DialecticAI framework itself.

        Collects: full @dialectical map of all components + development log.

        Returns:
            Text of the audit report from LLM.
        """
        context_parts = []

        dialectical_map = self._collect_dialectical_map()
        if dialectical_map:
            context_parts.append(
                f"### @dialectical map of the framework (all layers):\n{dialectical_map}"
            )
        else:
            context_parts.append("### @dialectical map: NO registered components")

        log_context = self._read_log(log_path or str(DEFAULT_LOG_PATH))
        if log_context:
            context_parts.append(
                f"### Development Log of the framework (development_log.md):\n{log_context}"
            )
        else:
            context_parts.append("### Development Log of the framework: MISSING OR EMPTY")

        context = "\n\n".join(context_parts)
        audit_mode = "AUDIT OF THE DialecticAI FRAMEWORK"

        self._iterations_since_audit = 0
        return await self._run_audit(audit_mode, context)

    async def investigate_contradiction(
        self,
        trace_path: str = "trace.jsonl",
        event_index: int = -1,
        event_type: Optional[str] = None,
    ) -> str:
        """
        Root-cause investigation of ONE specific contradiction event (dialectical_resolution_missing
        or leap_action_mismatch) from a trace.jsonl.

        This is a developer-facing diagnostic tool, not something the running agent invokes on
        itself: it does not modify code, does not re-run the agent, and does not resolve anything
        automatically. It formalizes the same backward-tracing a developer does by hand (as was
        done manually for the GigaChat repair-schema-blindness bug on 2026-09-13) -- reading the
        full prompt and raw response that produced the contradiction, plus the actual framework
        source code in the chain that processed them, and asking for a root-cause hypothesis:
        is the fault in the prompt wording, the provider's behavior/library limitations, or the
        parsing/engine code -- not just "the model was wrong."

        Args:
            trace_path: Path to trace.jsonl (must contain full forensic fields -- raw_response,
                provider_class, full_prompt -- as written by DialecticalEngine since 2026-09-13;
                older/thin events without these fields will produce a lower-quality investigation).
            event_index: Which matching event to investigate (default: -1, the most recent).
            event_type: Restrict to one event type ("dialectical_resolution_missing" or
                "leap_action_mismatch"); default None matches either.

        Returns:
            Text of the root-cause hypothesis from LLM (or the raw collected context if no LLM
            was configured).
        """
        events = self._read_contradiction_events(trace_path, event_type)
        if not events:
            return (
                f"[DialecticalAuditor] No contradiction events "
                f"({event_type or '/'.join(_CONTRADICTION_EVENT_TYPES)}) found in '{trace_path}'."
            )

        try:
            event = events[event_index]
        except IndexError:
            return (
                f"[DialecticalAuditor] event_index {event_index} out of range "
                f"({len(events)} matching events found)."
            )

        provider_class = event.get("provider_class", "")
        source_paths = list(_CORE_CHAIN_FILES)
        provider_file = _PROVIDER_FILE_MAP.get(provider_class)
        if provider_file and provider_file not in source_paths:
            source_paths.append(provider_file)
        source_context = self._read_source_files(source_paths)

        context = f"""### Contradiction event under investigation ({event.get('event_type', event_type or '?')}):
- Session: {event.get('session_id', '?')}
- Iteration: {event.get('iteration', '?')}
- Reason flagged by the engine: {event.get('reason', '(dialectical_resolution_missing: fields were empty)')}
- Provider class in use: {provider_class or '(not recorded)'}

### Full raw LLM response that triggered this event:
{event.get('raw_response', '(not recorded -- this event predates full forensic logging)')}

### Full prompt sent to the LLM for this turn:
{event.get('full_prompt', '(not recorded -- this event predates full forensic logging)')}

### Framework source code in the chain that produced/processed this response:
{source_context}
"""

        prompt = f"""You are investigating the ROOT CAUSE of one specific dialectical contradiction
that DialecticalEngine detected and could not (or did not) resolve on its own. This is a backward,
diagnostic investigation, not a fix -- do not propose a full rewrite, propose a specific, falsifiable
hypothesis: where in the chain (prompt wording, provider/library limitation, parsing code, engine
logic) did this actually originate? Cite the specific file and line/section if you can identify one.
Distinguish between "the model reasoned poorly" (not actionable by code changes) and "the framework
made poor reasoning more likely or failed to catch it" (actionable).

{context}

Report: (1) your root-cause hypothesis, (2) the specific file/mechanism you believe is responsible,
(3) whether this looks like a one-off model failure or a systemic gap the framework should close.
"""

        if self.llm is None:
            return "[DialecticalAuditor] LLM not specified -- context collected, analysis not performed.\n\n" + context

        print(f"\n[DialecticalAuditor] Investigating {event.get('event_type', event_type)} "
              f"(session={event.get('session_id', '?')}, iteration={event.get('iteration', '?')})...")
        try:
            return await self.llm.generate([{"role": "user", "content": prompt}])
        except Exception as e:
            return f"[DialecticalAuditor] LLM error: {e}"

    def notify_iteration(self) -> Optional[str]:
        """
        Called after each iteration of the agent by the engine.
        Returns a reminder string if it's time to run the audit, otherwise None.

        Used by DialecticalEngine automatically if the auditor is passed to it.
        """
        self._iterations_since_audit += 1
        if self._iterations_since_audit >= self.run_reminder_after_iterations:
            return (
                f"\n[DialecticalAuditor] {self._iterations_since_audit} iterations have passed "
                f"of the agent without an audit of the methodology.\n"
                f"Recommended: python -m dialectic_ai.cli.main audit [--config agent.json]\n"
            )
        return None

    # ─── Private methods ─────────────────────────────────────────────────────

    async def _run_audit(self, audit_mode: str, context: str) -> str:
        """Loads the prompt template, substitutes the context, and sends it to LLM."""
        methodology_product = self._read_methodology()   # dialectics_rules.md
        methodology_process = self._get_process_methodology()
        prompt_template = self._load_prompt_template()

        filled_prompt = (
            prompt_template
            .replace("{METHODOLOGY_PRODUCT}", methodology_product)
            .replace("{METHODOLOGY_PROCESS}", methodology_process)
            .replace("{AUDIT_MODE}", audit_mode)
            .replace("{CONTEXT}", context)
            # Backward compatibility: if the template still uses the old placeholder
            .replace("{METHODOLOGY}", methodology_product)
        )

        if self.llm is None:
            return (
                "[DialecticalAuditor] LLM not specified — context collected, analysis not performed.\n"
                "Please pass llm=GeminiLLM() to the constructor.\n\n"
                "Collected context:\n\n" + context
            )

        print(f"\n[DialecticalAuditor] Starting audit: {audit_mode}")
        print("[DialecticalAuditor] Sending context to LLM (may take 30-60 seconds)...")

        messages = [{"role": "user", "content": filled_prompt}]
        try:
            return await self.llm.generate(messages)
        except Exception as e:
            return f"[DialecticalAuditor] LLM error: {e}"

    def _load_prompt_template(self) -> str:
        if self.prompt_path.exists():
            return self.prompt_path.read_text(encoding="utf-8")
        # Minimal built-in fallback
        return (
            "You are an independent auditor. Mode: {AUDIT_MODE}.\n"
            "Methodology:\n{METHODOLOGY}\n\n"
            "Context:\n{CONTEXT}\n\n"
            "Provide a structured report with violations and recommendations."
        )

    def _read_methodology(self) -> str:
        """Reads dialectics_rules.md — standard for evaluating the PRODUCT (agent architecture)."""
        if self.methodology_path.exists():
            return self.methodology_path.read_text(encoding="utf-8")
        return "dialectics_rules.md not found."

    def _get_process_methodology(self) -> str:
        """
        Returns a detailed standard for evaluating the PROCESS of development.

        Contains 4 rules with specific criteria for evidence —
        what is considered confirmation and what is a declaration.
        Built into the code but can be overridden through subclassing.
        """
        return """\
Rule 1 — Derivation:
Each subsequent step of development must organically derive from the sum of the previous ones,
inheriting their features and limitations. It should not just precede — it should be generated by them.

Rule 2 — Collision with the world:
Each significant step must be immediately checked against reality
(execution, test, simulation). When a collision reveals a problem, it is resolved with reference
to industry best practices — but best practices are accepted or rejected consciously and
critically, not thoughtlessly.

Rule 3 — Reflection of the leap:
When transitioning to a fundamentally new architectural step, one must stop and assess
the nature of the transition itself: how it should actually occur, what alternative practices and paradigms exist for this stage. Not only the code is validated,
but also the direction of thought.

Rule 4 — Memory of development:
From the first step, a continuous light log of architectural decisions is maintained. Before each new
step, one must check both against the rules of methodology and this log, to not lose the vector.

Rule 5 — Driving to Contradiction (only for significant, Rule-3-level steps):
Development must be pushed to an explicit contradiction and its resolution, not stopped at
"problem -> fix." The entry must name: the Simplest process (connected to the task, generative of
the developing processes, itself connected back to it); the Development chain from abstract to
concrete (each step already potential in the previous one); the Opposite process (a process whose
own development does NOT require the simplest process to exist — this is not the same as an
alternative practice/library considered under Rule 2/3, which merely competes to solve the same
need); the Contradiction (simplest and opposite taken together in the unity of their development);
and the Leap (the process that resolves it, either by replacing both while absorbing their
development, or by making the contradiction's continued existence possible until such a replacement
appears).

CRITERIA FOR EVIDENCE (what to consider confirmation, not a declaration):
— Rule 1: in the structure of development_log.md / git history, there is a clear path of dependency
  of the new step on the functionality of the previous ones. Violation — a step without a traceable connection
  to the previous ones, or a "leap" without intermediate stages.
— Rule 2: the log contains a clear mention of "checked — result is such", a test or log
  of execution; there is a clear discussion of why a specific best practice was accepted or rejected.
  Violation — practice accepted without comment on the reason, or the step was not checked at all.
— Rule 3: for each major architectural transition (change of memory type, addition
  of a new tool, change of LLM provider, change of prompt) the log records
  considered alternatives and the reason for the choice. Violation — transition without a trace of reflection.
— Rule 4: there is a continuous, chronologically consistent log of decisions (development_log.md),
  updated during development, not written retrospectively. Violation — steps in the code
  or config without a record in the log, absence of dates, clear signs of retrospective recording.
— Rule 5: for each Rule-3-level significant step, the log names all five elements (Simplest process,
  Development chain, Opposite process, Contradiction, Leap) — not just a problem and its fix.
  Violation — a significant step recorded only as "Reality Check -> Transition Evaluation" without an
  Opposite process distinct from a considered alternative practice/library, or without an explicit
  Contradiction/Leap; also a violation if the "opposite process" named is actually just a competing
  implementation option for the same need rather than a process that does not require the simplest
  process at all.
— Rule 5 (runtime): since 2026-09-13, DialecticalEngine requires opposite_process/contradiction/leap
  on every finalized agent response (not only in development_log.md) and marks violations with a
  "dialectical_resolution_missing" trace event. If a trace.jsonl is provided, treat a nonzero rate of
  "dialectical_resolution_missing" events among "synthesize" events as direct runtime evidence of a
  Rule 5 violation, distinct from and complementary to the development-log-based check above.
"""

    def _read_log(self, log_path: str) -> str:
        p = Path(log_path)
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def _read_contradiction_events(self, trace_path: str, event_type: Optional[str]) -> list[dict]:
        """Reads trace.jsonl and returns the events matching the given (or any) contradiction type."""
        p = Path(trace_path)
        if not p.exists():
            return []
        wanted = (event_type,) if event_type else _CONTRADICTION_EVENT_TYPES
        events = []
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if data.get("event_type") in wanted:
                events.append(data)
        return events

    def _read_source_files(self, relative_paths: list[str], max_chars_per_file: int = 6000) -> str:
        """Reads framework source files (relative to the project root) for the investigation prompt."""
        project_root = Path(__file__).parent.parent.parent
        parts = []
        for rel_path in relative_paths:
            full_path = project_root / rel_path
            if not full_path.exists():
                parts.append(f"--- {rel_path} ---\n(file not found)")
                continue
            try:
                text = full_path.read_text(encoding="utf-8")
            except Exception as e:
                parts.append(f"--- {rel_path} ---\n(could not read: {e})")
                continue
            if len(text) > max_chars_per_file:
                text = text[:max_chars_per_file] + "\n... (truncated)"
            parts.append(f"--- {rel_path} ---\n{text}")
        return "\n\n".join(parts)

    def _collect_dialectical_map(self) -> str:
        """Imports all packages so that @dialectical fills the registry, then serializes."""
        try:
            import dialectic_ai.agent
            import dialectic_ai.core
            import dialectic_ai.engine
            import dialectic_ai.memory
            import dialectic_ai.multi
            import dialectic_ai.observability
            import dialectic_ai.reality  # noqa: F401 — side-effect: fills @dialectical registry
        except ImportError:
            pass

        items = get_dialectical_map()
        if not items:
            return ""

        lines = []
        for item in items:
            entry = (
                f"[Layer {item.layer}] {item.name}:\n"
                f"  Origin: {item.origin}\n"
                f"  Contradiction: {item.contradiction}\n"
                f"  Resolves: {item.resolves}\n"
                f"  Generates: {item.generates}\n"
                f"  Own contradictions: {item.own_contradictions}"
            )
            if item.simplest_process:
                entry += f"\n  Simplest process (Rule 5): {item.simplest_process}"
            if item.opposite_process:
                entry += f"\n  Opposite process (Rule 5): {item.opposite_process}"
            lines.append(entry)
        return "\n\n".join(lines)
