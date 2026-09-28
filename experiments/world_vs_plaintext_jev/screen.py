"""Step 3 of PREREGISTRATION.md: headroom screen (Jev only, condition 1, all 752 candidates), then the pool
(margin_screen < 0.5) and the N=60 sample (random.Random(42).sample over the pool in CSV row order).
Resumable: raw answers go to data/screen.jsonl as they arrive."""
from __future__ import annotations

import json
import random
import sys
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from common import (DATA, HERE, JEV_PRICE_PER_MTOK, JevAPIError, append_jsonl, jev_noul, load_items,  # noqa: E402
                    read_jsonl)

SCREEN = DATA / "screen.jsonl"
N_SELECT = 60
BUDGET_USD = 0.5  # screen-only guard; whole-experiment Jev budget is $1 (PREREGISTRATION.md)


def main() -> None:
    items = load_items()
    print(f"candidates: {len(items)}")
    done = {(r["id"], r["cand"]) for r in read_jsonl(SCREEN) if "noul" in r}
    todo = [(it, cand) for it in items for cand in ("true", "false") if (it["id"], cand) not in done]
    print(f"already done: {len(done)}, to do: {len(todo)}")

    def work(job):
        it, cand = job
        try:
            r = jev_noul(it["question"], it[cand])
            append_jsonl(SCREEN, {"id": it["id"], "cand": cand, **r})
        except JevAPIError as e:
            append_jsonl(SCREEN, {"id": it["id"], "cand": cand, "error": str(e)[:300]})

    if todo:
        with ThreadPoolExecutor(max_workers=8) as ex:
            list(ex.map(work, todo))

    rows = read_jsonl(SCREEN)
    ok = {(r["id"], r["cand"]): r for r in rows if "noul" in r}
    tokens = sum(r["input_tokens"] for r in ok.values())
    print(f"ok answers: {len(ok)}/{2 * len(items)}, input tokens {tokens}, "
          f"cost ~${tokens * JEV_PRICE_PER_MTOK / 1e6:.4f}")
    if tokens * JEV_PRICE_PER_MTOK / 1e6 > BUDGET_USD:
        print("BUDGET STOP"); return

    margins, missing = {}, []
    for it in items:
        t, f = ok.get((it["id"], "true")), ok.get((it["id"], "false"))
        if t is None or f is None:
            missing.append(it["id"]); continue
        margins[it["id"]] = t["noul"] - f["noul"]
    if missing:
        print(f"MISSING answers for {len(missing)} items (rerun to retry): {missing[:10]}..."); return

    def acc(ids):
        return sum(1.0 if margins[i] > 0 else 0.5 if margins[i] == 0 else 0.0 for i in ids) / len(ids)

    pool = [it["id"] for it in items if margins[it["id"]] < 0.5]
    print(f"pool (margin_screen < 0.5): {len(pool)} of {len(items)}")
    print(f"pair accuracy, all: {acc([it['id'] for it in items]):.3f}; in pool: {acc(pool):.3f}")
    n = min(N_SELECT, len(pool))
    selected = random.Random(42).sample(pool, n)
    by_id = {it["id"]: it for it in items}
    out = {"n_candidates": len(items), "pool_size": len(pool), "n_selected": n, "seed": 42,
           "screen_margin_rule": "< 0.5",
           "selected": [{"id": i, "type": by_id[i]["type"], "category": by_id[i]["category"]} for i in selected]}
    (HERE / "selected_items.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    (DATA / "screen_summary.json").write_text(json.dumps(
        {"pool_size": len(pool), "acc_all": acc([it["id"] for it in items]), "acc_pool": acc(pool),
         "input_tokens": tokens, "cost_usd": tokens * JEV_PRICE_PER_MTOK / 1e6}, indent=1), encoding="utf-8")
    print(f"selected {n} ids, first 6 (pilot): {selected[:6]}")


if __name__ == "__main__":
    main()
