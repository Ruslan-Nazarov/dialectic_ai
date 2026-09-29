"""Pilot / final report for world_vs_plaintext_jev: margins per item and condition, paired differences with
item-level bootstrap CIs (metrics_ext.bootstrap_ci_by_doc, 2000 resamples, seed 42), lengths, tokens, cost.
Usage: python report.py [--ids-from-texts]  (reports every item that has all 4 conditions answered)."""
from __future__ import annotations

import json
import statistics
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from common import DATA, JEV_PRICE_PER_MTOK, load_items, read_jsonl  # noqa: E402
from metrics_ext import bootstrap_ci_by_doc  # noqa: E402

CONDS = ["1_none", "2_world", "3_note", "4_poison"]


def main() -> None:
    by_id = {it["id"]: it for it in load_items()}
    log = [r for r in read_jsonl(DATA / "jev.jsonl") if "noul" in r]
    noul = {(r["id"], r["cond"], r["cand"]): r["noul"] for r in log}
    rows = []
    for tp in sorted((DATA / "texts").glob("*.json")):
        t = json.loads(tp.read_text(encoding="utf-8"))
        if "brief" not in t:
            continue
        i = t["id"]
        if not all((i, c, k) in noul for c in CONDS for k in ("true", "false")):
            continue
        row = {"doc": i, "t": t}
        for c in CONDS:
            row[f"nt_{c}"], row[f"nf_{c}"] = noul[(i, c, "true")], noul[(i, c, "false")]
            row[f"m_{c}"] = row[f"nt_{c}"] - row[f"nf_{c}"]
        rows.append(row)
    print(f"items with all 4 conditions: {len(rows)}\n")

    print("id    status  proc   L  | margin: none  world  note  poison | noul(true)/noul(false) none -> world / note / poison")
    for r in rows:
        t = r["t"]
        print(f"{r['doc']:<5} {t['world_status']:<8}{t['world_processes']:<4}{t['L']:<5}|        "
              f"{r['m_1_none']:+.2f} {r['m_2_world']:+.2f} {r['m_3_note']:+.2f} {r['m_4_poison']:+.2f}  | "
              f"{r['nt_1_none']:.2f}/{r['nf_1_none']:.2f} -> {r['nt_2_world']:.2f}/{r['nf_2_world']:.2f} / "
              f"{r['nt_3_note']:.2f}/{r['nf_3_note']:.2f} / {r['nt_4_poison']:.2f}/{r['nf_4_poison']:.2f}")

    def pair_acc(c):
        return statistics.mean(1.0 if r[f"m_{c}"] > 0 else 0.5 if r[f"m_{c}"] == 0 else 0.0 for r in rows)

    print("\nmean margin / pair accuracy by condition:")
    for c in CONDS:
        print(f"  {c:<9} margin {statistics.mean(r[f'm_{c}'] for r in rows):+.3f}   pair-acc {pair_acc(c):.3f}   "
              f"mean noul(true) {statistics.mean(r[f'nt_{c}'] for r in rows):.3f}  noul(false) {statistics.mean(r[f'nf_{c}'] for r in rows):.3f}")

    print("\npaired differences in margin (mean, 95% bootstrap CI by item):")
    for name, a, b in (("H1: world - none", "2_world", "1_none"), ("H2: world - note", "2_world", "3_note"),
                       ("descr: poison - none", "4_poison", "1_none")):
        ci = bootstrap_ci_by_doc(rows, lambda rs, a=a, b=b: statistics.mean(r[f"m_{a}"] - r[f"m_{b}"] for r in rs))
        print(f"  {name:<22} {ci['point']:+.3f}  [{ci['lo']:+.3f}, {ci['hi']:+.3f}]")
    sd = statistics.pstdev([r["m_2_world"] - r["m_3_note"] for r in rows]) if len(rows) > 1 else float("nan")
    print(f"  sd of per-item (world - note) margin difference: {sd:.3f}")

    print("\ncost / size:")
    build_tok = [(r["t"]["build_usage"] or {}) for r in rows]
    tot_build = sum(b.get("prompt", 0) + b.get("completion", 0) for b in build_tok)
    tot_gen = sum(r["t"]["gen_usage"]["prompt"] + r["t"]["gen_usage"]["completion"] for r in rows)
    print(f"  builder tokens (worlds): {tot_build}  (mean {tot_build / max(len(rows), 1):.0f}/world, "
          f"calls mean {statistics.mean((b.get('calls') or 0) for b in build_tok):.1f})")
    print(f"  note+poison tokens (gpt-5): {tot_gen}  (mean {tot_gen / max(len(rows), 1):.0f}/item for both texts)")
    print(f"  mean build seconds: {statistics.mean(r['t']['build_seconds'] for r in rows):.0f}")
    print(f"  length ratio note/L: {[round(len(r['t']['note']) / r['t']['L'], 2) for r in rows]}")
    print(f"  length ratio poison/L: {[round(len(r['t']['poison']) / r['t']['L'], 2) for r in rows]}")
    statuses = {}
    for r in rows:
        statuses[r["t"]["world_status"]] = statuses.get(r["t"]["world_status"], 0) + 1
    print(f"  world statuses: {statuses}")
    itok = {}
    for r in log:
        itok.setdefault(r["cond"], []).append(r["input_tokens"])
    print("  Jev input tokens per call by condition:",
          {c: round(statistics.mean(v)) for c, v in sorted(itok.items())})
    total = sum(r["input_tokens"] for r in log)
    print(f"  Jev total (incl. all logged calls): {total} tokens, ~${total * JEV_PRICE_PER_MTOK / 1e6:.4f}")


if __name__ == "__main__":
    main()
