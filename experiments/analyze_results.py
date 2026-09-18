import json
import sys
from collections import defaultdict

def analyze(filename):
    results = defaultdict(lambda: defaultdict(list))
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line)
            results[data['case_id']][data['facet']].append(data['decision'])
            
    print(f"--- Analysis for {filename} ---")
    for case, facets in results.items():
        print(f"Case: {case}")
        valid_dev_count = 0
        runs_total = max([len(v) for v in facets.values()])
        
        # Calculate case-level validity per run (assuming aligned runs if completed)
        # We'll just print facet majorities
        for facet, decisions in facets.items():
            trues = sum(1 for d in decisions if d is True)
            falses = len(decisions) - trues
            majority = True if trues > falses else False
            
            if facet == "workflow_only":
                passed = not majority
            else:
                passed = majority
                
            print(f"  {facet}: {majority} ({trues}T/{falses}F) -> {'PASS' if passed else 'FAIL'}")
        print()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        analyze(sys.argv[1])
