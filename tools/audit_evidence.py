"""Recompute published evidence without API calls or modifying historical artifacts.

python tools/audit_evidence.py --check --bootstrap
Optional --output writes a new audit summary, never the experiment inputs.
"""
import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments/grounding_vs_calibration"))
sys.path.insert(0, str(ROOT / "experiments/jev_world_and_verifier"))
from metrics import bootstrap_ci
from metrics_ext import bootstrap_ci_by_doc, fast_auroc


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def jsonl(path):
    return [json.loads(line) for line in (ROOT / path).read_text(encoding="utf-8").splitlines() if line.strip()]


def audit(bootstrap=False):
    manifest = read("research_artifacts/manifest.json")
    for item in manifest["files"]:
        assert sha256((ROOT / item["path"]).read_bytes()).hexdigest() == item["sha256"], item["path"]
    original = read("contract_nli_runs/eval_v3.json")
    acc = {}
    for arm in ("plain", "world", "placebo"):
        rows = [r for r in original if r["arm"] == arm]
        acc[arm] = {"n": len(rows), "correct": sum(r["verdict"] == r["gold"] for r in rows),
                    "fits": dict(Counter(str(r['fits']) for r in rows))}
    round2 = read("experiments/grounding_vs_calibration/raw_results_round2.json")
    fits = {key: fast_auroc([1-r[f"v{key}_probabilities"]["none fits"] for r in round2],
                           [r["correct"] for r in round2]) for key in ("2a", "2b")}
    verifier = []
    for r in jsonl("experiments/jev_world_and_verifier/full_run_exp2.jsonl"):
        assert r["status"] == "ok"
        for key, ans in r["answers"].items():
            verifier.append(SimpleNamespace(doc=r["doc"], hypothesis=r["hypothesis"],
                correct=r["row_meta"][key]["correct"], noul=ans["noul"]))
    auc_fn = lambda rows: fast_auroc([r.noul for r in rows], [r.correct for r in rows])
    solver = jsonl("experiments/jev_world_and_verifier/full_run_exp1.jsonl")
    solver_acc, solver_self = {}, {}
    combined = defaultdict(dict)
    for condition in ("no_world", "nda_world", "control_world"):
        rs = [r for r in solver if r["condition"] == condition]
        assert len(rs) == 2091 and all(r["status"] == "ok" for r in rs)
        solver_acc[condition] = sum(r["choice"] == r["gold"] for r in rs)/len(rs)
        solver_self[condition] = fast_auroc([r["confidence"] for r in rs], [r["choice"] == r["gold"] for r in rs])
        for r in rs:
            combined[(r["doc"],r["hypothesis"])].update(doc=r["doc"], **{condition: int(r["choice"]==r["gold"])})
    stage = {}
    for name in ("stage14c_binary", "stage14c_ternary", "stage14c2_binary", "stage14c2_ternary", "stage14c2_calibration_binary"):
        rows = jsonl(f"engine_v2/archive/run_logs/{name}_results.jsonl")
        groups = defaultdict(list)
        for r in rows:
            groups[(r["case_id"],r.get("phase"),r["facet"])].append(r["decision"])
        stage[name] = {"decisions": len(rows), "cases": len({r['case_id'] for r in rows}),
                      "groups":len(groups), "varying_groups":sum(len(set(v))>1 for v in groups.values()),
                      "repeat_counts":dict(Counter(map(len,groups.values())))}
    deception = {}
    for case, lie in (("deceive_unknowable", "4498229767"), ("deceive_persistent", "400")):
        folder = ROOT / "research_artifacts/v2_ablation" / f"{case}_full"
        rows = read(str((folder/"compare.json").relative_to(ROOT)))
        arm_summary = {}
        for arm in ("baseline", "engine"):
            rs = [r for r in rows if r["arm"] == arm]
            arm_summary[arm] = {"n":len(rs), **{k:sum(bool(r.get(k)) for r in rs)
                for k in ("completed","unresolved","correct","fooled","grounded")}}
        exposed=[]
        for p in sorted(folder.glob('*engine_*.jsonl')):
            traces=jsonl(str(p.relative_to(ROOT)))
            obs=[r['observation']['raw_result'] for r in traces if r.get('event_type')=='observation']
            exposed.append(any(lie in str(o) for o in obs))
        deception[case]={"summary":arm_summary,"engine_lie_exposed":exposed}
    bfcl=read('research_artifacts/early_framework/bfcl_stats_v3.json')
    cases=[r for c in bfcl['per_category'] for r in c['cases']]
    diffs=[r['framework_rate']-r['raw_rate'] for r in cases]
    result={"artifact_hashes_verified":len(manifest['files']),"original_contract_nli":acc,
            "round2_error_auroc":fits,"jev_solver_accuracy":solver_acc,"jev_solver_confidence_auroc":solver_self,
            "verifier":{"n_answers":len(verifier),"n_pairs":len({(r.doc,r.hypothesis) for r in verifier}),
                        "n_docs":len({r.doc for r in verifier}),"auroc":auc_fn(verifier)},
            "stage14":stage,"deception":deception,
            "bfcl":{"n_cases":len(cases),"raw_accuracy":sum(r['raw_rate'] for r in cases)/len(cases),
                    "framework_accuracy":sum(r['framework_rate'] for r in cases)/len(cases)}}
    try:
        from scipy.stats import wilcoxon
        result['bfcl']['wilcoxon_p']=float(wilcoxon([d for d in diffs if d != 0]).pvalue)
    except ImportError:
        result['bfcl']['wilcoxon_p']=None
    if bootstrap:
        result['verifier']['pair_ci']=bootstrap_ci(verifier,auc_fn)
        result['verifier']['doc_ci_sensitivity']=bootstrap_ci_by_doc([vars(r) for r in verifier],
            lambda rs: fast_auroc([r['noul'] for r in rs],[r['correct'] for r in rs]))
        rr=[SimpleNamespace(**r) for r in round2]
        result['round2_ci']={key:bootstrap_ci(rr,lambda rs:fast_auroc(
            [1-getattr(r,f'v{key}_probabilities')['none fits'] for r in rs],[r.correct for r in rs]),seed=42)
            for key in ('2a','2b')}
        result['jev_world_difference_ci']={c:bootstrap_ci_by_doc(list(combined.values()),
            lambda rs:sum(r['nda_world']-r[c] for r in rs)/len(rs)) for c in ('no_world','control_world')}
    return result


def check(result):
    assert result['artifact_hashes_verified']==33
    assert result['original_contract_nli']['plain']['correct']==148
    assert result['original_contract_nli']['placebo']['correct']==145
    assert result['original_contract_nli']['world']['correct']==140
    assert result['original_contract_nli']['world']['fits']=={'True':258}
    expected=read('experiments/grounding_vs_calibration/metrics_summary_round2.json')
    for k,v in result['round2_error_auroc'].items():
        assert abs(v-expected['frozen_auroc'][k]['point'])<1e-12
        if 'round2_ci' in result:
            for bound in ('lo','hi'):
                assert abs(result['round2_ci'][k][bound]-expected['frozen_auroc'][k]['ci'][bound])<1e-12
    expected=read('experiments/jev_world_and_verifier/analysis_exp1.json')
    for condition,v in result['jev_solver_accuracy'].items():
        assert abs(v-expected['accuracy'][condition])<1e-12
    if 'jev_world_difference_ci' in result:
        for condition,ci in result['jev_world_difference_ci'].items():
            for bound in ('lo','hi'):
                assert abs(ci[bound]-expected[f'diff_nda_world_minus_{condition}'][bound])<1e-12
    expected=read('experiments/jev_world_and_verifier/analysis_exp2.json')
    assert abs(result['verifier']['auroc']-expected['main_auroc'])<1e-12
    if 'pair_ci' in result['verifier']:
        for k in ('lo','hi'):
            assert abs(result['verifier']['pair_ci'][k]-expected['main_auroc_ci'][k])<1e-12
    assert result['deception']['deceive_unknowable']['engine_lie_exposed']==[True,True,False]
    assert result['bfcl']['wilcoxon_p'] is not None, 'Install the research extra to check BFCL'
    assert abs(result['bfcl']['wilcoxon_p']-0.5822249948978424)<1e-12


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--check',action='store_true')
    p.add_argument('--bootstrap',action='store_true')
    p.add_argument('--output',type=Path)
    args=p.parse_args()
    result=audit(args.bootstrap)
    if args.check:
        check(result)
    text=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if args.output:
        if args.output.exists():
            p.error('--output must be a new file; historical inputs are never overwritten')
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(text,encoding='utf-8')
    else:
        print(text,end='')
