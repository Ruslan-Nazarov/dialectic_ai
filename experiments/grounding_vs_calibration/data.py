"""Load the 258 world-arm answers, join gold labels, compute correctness."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVAL_V3 = ROOT / "contract_nli_runs" / "eval_v3.json"
GOLD_FILE = ROOT / "live_runs" / "contract_nli" / "contract-nli" / "test.json"
WORLD_FILE = (
    ROOT
    / "live_runs"
    / "v3_worlds"
    / "договоры_о_неразглашении_nda_одна_сторона_раскрывает_другой_"
    / "v1.json"
)


@dataclass
class Answer:
    doc: int
    hypothesis: str
    group: str
    rep: int
    gold: str
    verdict: str
    fits: bool | None
    fit_note: str
    fit_ids: list[str]
    answer: str
    seconds: float
    correct: bool


def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_gold_map(gold_file: Path = GOLD_FILE) -> dict[tuple[int, str], str]:
    """(doc_id, hypothesis_key) -> gold choice, straight from ContractNLI test.json."""
    data = _load_json(gold_file)
    out: dict[tuple[int, str], str] = {}
    for doc in data["documents"]:
        anns = doc["annotation_sets"][0]["annotations"]
        for hyp_key, ann in anns.items():
            out[(doc["id"], hyp_key)] = ann["choice"]
    return out


def load_world(world_file: Path = WORLD_FILE) -> dict:
    return _load_json(world_file)


def active_process_ids(world: dict) -> list[str]:
    """Process ids with status == 'active' only (excludes 'retired'). 152 active / 3 retired of 155 total."""
    return [pid for pid, p in world["processes"].items() if p.get("status") == "active"]


def load_world_answers(
    eval_file: Path = EVAL_V3, gold_file: Path = GOLD_FILE, verify_gold: bool = True
) -> list[Answer]:
    rows = _load_json(eval_file)
    world_rows = [r for r in rows if r["arm"] == "world"]
    if len(world_rows) != 258:
        raise ValueError(f"expected 258 world-arm rows, got {len(world_rows)}")

    gold_map = load_gold_map(gold_file) if verify_gold else None

    answers = []
    for r in world_rows:
        gold = r["gold"]
        if gold_map is not None:
            true_gold = gold_map.get((r["doc"], r["hypothesis"]))
            if true_gold is not None and true_gold != gold:
                raise ValueError(
                    f"gold mismatch doc={r['doc']} hyp={r['hypothesis']}: "
                    f"eval_v3.json says {gold!r}, test.json says {true_gold!r}"
                )
        answers.append(
            Answer(
                doc=r["doc"],
                hypothesis=r["hypothesis"],
                group=r["group"],
                rep=r["rep"],
                gold=gold,
                verdict=r["verdict"],
                fits=r.get("fits"),
                fit_note=r.get("fit_note", ""),
                fit_ids=r.get("fit_ids") or [],
                answer=r.get("answer", ""),
                seconds=r.get("seconds", 0.0),
                correct=(r["verdict"] == gold),
            )
        )
    return answers


def sanity_check_accuracy(answers: list[Answer]) -> float:
    """Recomputed accuracy over all 258 world-arm rows (129 pairs x 2 reps).

    Must reconcile with contract_nli_runs/eval_v3.md's reported 54% (world column, ALL row).
    """
    acc = sum(a.correct for a in answers) / len(answers)
    return acc


if __name__ == "__main__":
    answers = load_world_answers()
    acc = sanity_check_accuracy(answers)
    print(f"n={len(answers)} accuracy={acc:.4f} ({acc*100:.1f}%)")
    pairs = {(a.doc, a.hypothesis) for a in answers}
    print(f"unique pairs={len(pairs)}")
