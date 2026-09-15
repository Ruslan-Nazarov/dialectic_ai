import json
import os
import subprocess
from datasets import load_dataset

def main():
    print("Fetching GAIA2 dataset from HuggingFace...")
    # GAIA2 validation split
    dataset = load_dataset("meta-agents-research-environments/gaia2", "ambiguity", split="validation")
    
    scenarios_to_run = []
    excluded_id = "scenario_universe_23_iy0pbp"
    
    print(f"Filtering out {excluded_id} and selecting 10 unseen scenarios...")
    for row in dataset:
        # ARE scenario structure usually contains "id" or "name" in the row
        row_id = row.get("id") or row.get("scenario_id") or row.get("name")
        if not row_id:
            # Sometime the whole json is a string
            pass
            
        # Simplest way: just check if the excluded_id is anywhere in the row string representation
        row_str = str(row)
        if excluded_id not in row_str:
            scenarios_to_run.append(row)
            if len(scenarios_to_run) >= 10:
                break
                
    if len(scenarios_to_run) < 10:
        print(f"Warning: Only found {len(scenarios_to_run)} scenarios.")
        
    os.makedirs("benchmarks/gaia2/temp", exist_ok=True)
    temp_file = "benchmarks/gaia2/temp/10_scenarios.jsonl"
    
    with open(temp_file, "w", encoding="utf-8") as f:
        for s in scenarios_to_run:
            f.write(json.dumps(s) + "\n")
            
    print(f"Saved 10 scenarios to {temp_file}")
    
    # Now run ARE benchmark on these 10 scenarios
    # using our runner (which patches AgentBuilder)
    cmd = [
        "python", "-m", "benchmarks.gaia2.runner",
        "--limit", "10",
        # We need to tell runner.py to use this file instead of --hf-dataset
        # But runner.py hardcodes --hf-dataset. We need to modify runner.py or just call are-benchmark directly
        # Wait, runner.py uses are_args. Let's just modify runner.py to accept custom are_args.
    ]
    print("Script prepared. Run `benchmarks/gaia2/runner.py` with modified args when ready.")

if __name__ == "__main__":
    main()
