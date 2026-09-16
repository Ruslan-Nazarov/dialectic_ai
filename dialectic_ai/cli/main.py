"""
dialectic_ai/cli/main.py

DIALECTICAL DESCRIPTION:
  Origin: All components of the framework (Layers 0-5) are scattered across files.
    Custom scripts need to be written to work with them.
  Contradiction: Powerful internal architecture is inaccessible without a simple interface.
    The user is forced to understand the code of each module instead of solving applied tasks.
  How it solves: A single entry point in the CLI (`dialectic` or `python -m dialectic_ai.cli.main`):
    - `map`: displays the philosophical-dialectical map of all layers of the system;
    - `dashboard`: launches the observability web interface;
    - `eval`: performs an automatic audit of dialectical compliance based on traces;
    - `tutor`: launches a ready-made tutor agent in interactive mode.
  What it leads to: Quick deployment, convenient demonstration at hackathons, high DX.
  Its own contradictions: The CLI interface abstracts the internals; a developer may
    lose direct understanding of component interactions if they only use the CLI.
"""
import sys
import argparse
from pathlib import Path

# Imports will be loaded dynamically where needed

from dialectic_ai.core.dialectical import get_dialectical_map, print_dialectical_card, install_dialectical_excepthook
from dialectic_ai.observability.tracer import TraceReader
from dialectic_ai.observability.evaluator import AgentEvaluator
from dialectic_ai.observability.auditor import DialecticalAuditor
try:
    from dialectic_observability.server import run as run_dashboard_server
except ImportError:
    run_dashboard_server = None


def cmd_map(args):
    """Outputs the dialectical map of the framework architecture."""
    # Ensure all modules are imported to fill the dialectical metadata registry
    import dialectic_ai.core
    import dialectic_ai.agent
    import dialectic_ai.memory
    import dialectic_ai.reality
    import dialectic_ai.engine
    import dialectic_ai.multi
    import dialectic_ai.observability
    
    items = get_dialectical_map()
    if args.layer is not None:
        items = [item for item in items if item.layer == args.layer]

    print("\n" + "=" * 70)
    print("  PHILOSOPHICAL-DIALECTICAL MAP OF DIALECTIC-AI FRAMEWORK")
    print("=" * 70)
    print(f"Total registered components: {len(items)}\n")

    current_layer = -1
    layer_names = {
        0: "Layer 0: Foundation (Core, Types, Logger)",
        1: "Layer 1: Agent and Memory (Identity & Memory)",
        2: "Layer 2: Confrontation with Reality (Reality & Tools)",
        3: "Layer 3: Orchestration Engine (Engine Enforcement)",
        4: "Layer 4: Multi-Agent (Multi-Agent Protocol & Router)",
        5: "Layer 5: Observability (Observability, Tracing, Dashboard)",
        6: "Layer 6: Developer Experience (CLI, Examples, API)",
    }

    for item in items:
        if item.layer != current_layer:
            current_layer = item.layer
            layer_title = layer_names.get(current_layer, f"Layer {current_layer}")
            print(f"\n{'─'*70}")
            print(f"🔷 {layer_title}")
            print(f"{'─'*70}")

        print(f"\n📦 Class: {item.name}")
        print(f"  📍 Origin:   {item.origin}")
        print(f"  ⚡ Contradiction:    {item.contradiction}")
        print(f"  ✅ Resolution:      {item.resolves}")
        print(f"  ➡️  Generates:       {item.generates}")
        print(f"  🔄 Own Contradictions:    {item.own_contradictions}")

    print("\n" + "=" * 70 + "\n")


def cmd_dashboard(args):
    """Launches the web dashboard."""
    if run_dashboard_server is None:
        print("[-] The dialectic_observability package is not installed.")
        print("    Install it to run the dashboard (e.g., pip install dialectic-observability).")
        sys.exit(1)
    run_dashboard_server(host=args.host, port=args.port, trace_file=args.trace)


def cmd_eval(args):
    """Runs an evaluation of the session trace."""
    trace_path = Path(args.trace)
    if not trace_path.exists():
        print(f"[-] Trace file '{args.trace}' not found.")
        sys.exit(1)

    reader = TraceReader(str(trace_path))
    evaluator = AgentEvaluator(reader)
    report = evaluator.evaluate_session(args.session)

    print("\n" + "=" * 60)
    print("  DIALECTICAL AUDIT REPORT OF SESSION")
    print("=" * 60)
    print(f"Session:                  {report.session_id}")
    print(f"Dialectical Score:        {report.dialectical_score * 100:.1f}%")
    print(f"Reality Grounding:       {report.reality_grounding_score * 100:.1f}%")
    print(f"Synthesis achieved:       {'Yes ✅' if report.synthesized else 'No ❌'}")
    print(f"Iterations:               {report.iterations_count}")
    print(f"Memory enriched:          {'Yes ✅' if report.memory_updated else 'No ❌'}")

    if report.violations:
        print("\nDetected violations of the dialectical method:")
        for v in report.violations:
            print(f"  ⚠️ {v}")
    else:
        print("\nNo violations detected. The dialectical cycle was executed flawlessly. ✨")

    print(f"\nCall details: {report.details}")
    print("=" * 60 + "\n")


def cmd_audit(args):
    """
    Dialectical audit: checks the agent and/or development process
    for compliance with the 4 rules of the methodology.

    Two independent analyses:
      1. PRODUCT — architectural decisions within the agent
      2. PROCESS — how decisions were made (development_log.md)
    """
    import asyncio

    # Define LLM (if not --no-llm). GigaChat first: it's the provider this project's
    # own .env/HANDOFF.md documents as actually reliable; Gemini's free tier was
    # observed returning 503 UNAVAILABLE under load this session (see CODE_REVIEW.md,
    # Layer 5), so falling back to it first was likely to silently degrade to
    # context-only mode on this project's own configured credentials.
    llm = None
    if not args.no_llm:
        try:
            from dialectic_ai.integrations.gigachat.llm import GigaChatLLM
            llm = GigaChatLLM()
            print("[Audit] LLM: GigaChat")
        except Exception:
            try:
                from dialectic_ai.integrations.gemini.llm import GeminiLLM
                llm = GeminiLLM()
                print("[Audit] LLM: Gemini")
            except Exception:
                try:
                    from dialectic_ai.integrations.openai.llm import OpenAILLM
                    llm = OpenAILLM()
                    print("[Audit] LLM: OpenAI/OpenRouter")
                except Exception:
                    print("[Audit] LLM not found — only the assembled context will be output.")

    auditor = DialecticalAuditor(llm=llm)

    if args.investigate is not None:
        # Root-cause investigation of one contradiction event -- diagnostic only, does not
        # modify code or re-run the agent.
        report = asyncio.run(auditor.investigate_contradiction(
            trace_path=args.trace,
            event_index=args.investigate,
        ))
        print("\n" + "=" * 70)
        print("  DIALECTICAL AUDIT — CONTRADICTION INVESTIGATION")
        print("=" * 70)
        print(report)
        print("=" * 70 + "\n")
        return

    if args.framework:
        # Audit of the framework itself
        report = asyncio.run(auditor.audit_framework(log_path=args.log))
    else:
        # Audit of the developing agent
        report = asyncio.run(auditor.audit_agent(
            config_path=args.config,
            trace_path=args.trace,
            log_path=args.log,
        ))

    # Output report
    print("\n" + "=" * 70)
    print("  DIALECTICAL AUDIT — REPORT")
    print("=" * 70)
    print(report)
    print("=" * 70 + "\n")

    # Save report to file if --output is specified
    if args.output:
        out_path = Path(args.output)
        out_path.write_text(report, encoding="utf-8")
        print(f"[Audit] Report saved: {out_path.absolute()}")


def cmd_run(args):
    """Launches a declarative agent from the config file."""
    from dialectic_ai.cli.config_parser import load_agent_from_config
    from dialectic_ai.engine import DialecticalEngine
    from dialectic_ai.core.schema import AgentInput
    import uuid
    
    try:
        agent = load_agent_from_config(args.config)
        # Get max_iterations from the file (read again, as the parser currently returns only the agent)
        import json
        with open(args.config, "r", encoding="utf-8") as f:
            config = json.load(f)
        max_iterations = config.get("max_iterations", 3)
        
        engine = DialecticalEngine(agent, max_iterations=max_iterations)
        
        print("\n" + "=" * 60)
        print(f"  AGENT LAUNCHED ({config.get('name', 'DeclarativeAgent')})")
        print("=" * 60)
        print("Type 'exit' to quit.\n")
        
        import asyncio
        async def _repl_loop():
            session_id = str(uuid.uuid4())
            while True:
                try:
                    user_text = await asyncio.to_thread(input, "You: ")
                    if user_text.strip().lower() == "exit":
                        break
                    if not user_text.strip():
                        continue
                    
                    inp = AgentInput(user_message=user_text, session_id=session_id)
                    result = await engine.run(inp)
                    
                    print(f"\nAgent: {result.response}\n")
                except (KeyboardInterrupt, EOFError):
                    break
        asyncio.run(_repl_loop())
    except Exception as e:
        print(f"[-] Error launching agent: {e}")
        sys.exit(1)


def cmd_create(args):
    """Interactive agent creation wizard."""
    from dialectic_ai.cli.creator import run_interactive_creator
    run_interactive_creator()


def load_env():
    """Reads the .env file using python-dotenv."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass


def main():
    # Several CLI code paths print emoji (creator.py's wizard, dialectical.py's
    # architectural-error banner). The default console encoding on non-English
    # Windows locales is a narrow codepage (e.g. cp1251), not UTF-8, which
    # crashes those prints outright -- see development_log.md, 2026-09-15.
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    install_dialectical_excepthook()
    load_env()
    parser = argparse.ArgumentParser(
        prog="dialectic",
        description="DialecticAI Framework CLI — a framework for creating AI agents based on dialectical principles",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: create
    p_create = subparsers.add_parser("create", help="Interactive wizard for creating a new agent")

    # Command: audit
    p_audit = subparsers.add_parser(
        "audit",
        help="Dialectical audit of the agent/framework for compliance with the methodology"
    )
    p_audit.add_argument(
        "--config", default=None,
        help="Path to the JSON config of the developing agent (optional)"
    )
    p_audit.add_argument(
        "--trace", default="trace.jsonl",
        help="Path to the agent's trace file (default: trace.jsonl)"
    )
    p_audit.add_argument(
        "--log", default=None,
        help="Path to development_log.md (default: searches in the project root)"
    )
    p_audit.add_argument(
        "--framework", action="store_true",
        help="Audit the DialecticAI framework itself (not a specific agent)"
    )
    p_audit.add_argument(
        "--no-llm", action="store_true",
        help="Only assemble context without sending to LLM (offline mode)"
    )
    p_audit.add_argument(
        "--output", default=None,
        help="Save the report to a file (e.g., audit_report.md)"
    )
    p_audit.add_argument(
        "--investigate", nargs="?", const=-1, type=int, default=None,
        help="Root-cause investigation of one contradiction event (dialectical_resolution_missing / "
             "leap_action_mismatch) from --trace, by index (default: most recent, i.e. -1). "
             "Diagnostic only -- produces a hypothesis, does not modify code or re-run the agent."
    )

    # Command: map
    p_map = subparsers.add_parser("map", help="Output the philosophical-dialectical map of all components")
    p_map.add_argument("--layer", type=int, default=None, help="Filter by layer number (0-6)")

    # Command: dashboard
    p_dash = subparsers.add_parser("dashboard", help="Launch the Observability web dashboard")
    p_dash.add_argument("--port", type=int, default=7860, help="Server port (default: 7860)")
    p_dash.add_argument("--host", default="localhost", help="Server host")
    p_dash.add_argument("--trace", default="trace.jsonl", help="Path to the trace file")

    # Command: eval
    p_eval = subparsers.add_parser("eval", help="Evaluate the quality of adherence to the dialectical cycle")
    p_eval.add_argument("--trace", default="trace.jsonl", help="Path to the trace file")
    p_eval.add_argument("--session", default=None, help="Session identifier (default: entire database)")


    # Command: run
    p_run = subparsers.add_parser("run", help="Run an agent from the JSON configuration file")
    p_run.add_argument("config", help="Path to the configuration file (e.g., agent.json)")

    args = parser.parse_args()

    if args.command == "audit":
        cmd_audit(args)
    elif args.command == "map":
        cmd_map(args)
    elif args.command == "dashboard":
        cmd_dashboard(args)
    elif args.command == "eval":
        cmd_eval(args)
    elif args.command == "run":
        cmd_run(args)
    elif args.command == "create":
        cmd_create(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
