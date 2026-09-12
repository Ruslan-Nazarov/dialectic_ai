import sys
import argparse
from unittest.mock import patch
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
    parser.add_argument("--limit", type=int, default=1, help="Number of tasks to run")
    parser.add_argument("--dry-run", action="store_true", help="Run without calling LLM")
    
    # Parse known args so we don't crash on other args we might add later
    args, unknown = parser.parse_known_args()
    
    # Эмулируем CLI-команду для ARE benchmark (заменяем gaia2-run на run)
    are_args = [
        "are-benchmark",
        "run",
        "-a", "default",
        "--hf-dataset", "meta-agents-research-environments/gaia2",
        "--hf-split", "validation",
        "--config", "ambiguity",
        "--limit", str(args.limit),
        "--num_runs", "1",
        "--executor_type", "thread",
    ]
    
    print(f"Starting GAIA2 benchmark via ARE (limit={args.limit}, dry-run={args.dry_run})")
    
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
