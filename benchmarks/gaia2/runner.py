import sys
import argparse
import signal
from unittest.mock import patch

# Windows compatibility wrapper for ARE SIGALRM timeout
if not hasattr(signal, 'SIGALRM'):
    setattr(signal, 'SIGALRM', 14)  # mock constant
    
    _original_signal = signal.signal
    def _mock_signal(sig, handler):
        if sig == 14:
            return None
        return _original_signal(sig, handler)
    signal.signal = _mock_signal
    
    if not hasattr(signal, 'alarm'):
        setattr(signal, 'alarm', lambda seconds: None)

from are.simulation.benchmark.cli import main as are_benchmark_main
from are.simulation.agents.agent_builder import AgentBuilder
from benchmarks.gaia2.adapter import DialecticAREAgent

import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

def custom_agent_build(self, agent_config, env=None, mock_responses=None):
    # Returns our custom agent regardless of the config
    return DialecticAREAgent()

def main():
    parser = argparse.ArgumentParser(description="GAIA2 Runner for DialecticAI")
    parser.add_argument("--limit", type=int, default=11, help="Number of tasks to run")
    parser.add_argument("--dry-run", action="store_true", help="Run without calling LLM")
    parser.add_argument(
        "--config", default="ambiguity",
        choices=["adaptability", "ambiguity", "demo", "execution", "mini", "search", "time"],
        help=(
            "GAIA2 capability config to run. 'ambiguity' (the default) is the hardest category -- it "
            "specifically tests recognizing under-specification, and is where every failure investigated "
            "in development_log.md's 2026-09-14/15 entries came from. 'execution' tests straightforward, "
            "clearly-specified tool use and is a fairer test of 'does the agent do useful things correctly' "
            "without also demanding it correctly judge what's ambiguous. 'demo' is a 3-scenario smoke check."
        ),
    )

    # Parse known args so we don't crash on other args we might add later
    args, unknown = parser.parse_known_args()
    
    import os
    if args.dry_run:
        os.environ["DRY_RUN"] = "1"
    
    # Эмулируем CLI-команду для ARE benchmark (заменяем gaia2-run на run)
    are_args = [
        "are-benchmark",
        "run",
        "-a", "default",
        "--hf-dataset", "meta-agents-research-environments/gaia2",
        "--hf-split", "validation",
        "--config", args.config,
        "--limit", str(args.limit),
        "--num_runs", "1",
        "--executor_type", "thread",
        "--max_concurrent_scenarios", "1",
        # Default judge (HF Inference, meta-llama/Meta-Llama-3.3-70B-Instruct) has no
        # credentials configured anywhere in this environment and fails every call
        # with an auth error, silently turning every scenario's online validation
        # into a hard "Invalid". Point the judge at Groq instead, using the API key
        # already present in .env. gpt-oss-120b is the strongest model this key
        # currently has access to (verified live).
        "--judge_model", "openai/gpt-oss-120b",
        "--judge_provider", "groq",
    ]
    
    print(f"Starting GAIA2 benchmark via ARE (config={args.config}, limit={args.limit}, dry-run={args.dry_run})")
    
    # Monkey patch the AgentBuilder to return our agent
    with patch.object(AgentBuilder, 'build', new=custom_agent_build):
        # Override sys.argv so click uses our arguments
        sys.argv = are_args
        
        try:
            are_benchmark_main()
        except SystemExit as e:
            # Click exits automatically
            if e.code != 0:
                print(f"ARE Benchmark exited with code {e.code}")

if __name__ == "__main__":
    main()
