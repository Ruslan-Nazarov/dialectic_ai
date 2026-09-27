"""Load the 258 world-arm answers, join gold labels, compute correctness."""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXP_DIR = Path(__file__).resolve().parent
EVAL_V3 = ROOT / "contract_nli_runs" / "eval_v3.json"
GOLD_FILE = EXP_DIR / "data" / "contract-nli" / "test.json"
WORLD_FILE = EXP_DIR / "data" / "world_nda_v1.json"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


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
    if not gold_file.exists():
        raise FileNotFoundError(
            f"{gold_file} not found. Run `python download_contract_nli.py` first "
            "(fetches the official CC BY 4.0 dataset; not committed to this repo)."
        )
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


def process_description(pid: str, world: dict) -> str:
    """Id plus its actual formulation (source -> target, statement), for variant 2's process list.

    Bare ids (e.g. "Ib13b23") carry no meaning to a model with no other access to the world; listing
    only ids means the model is being asked whether an answer's reasoning "engages" 152 opaque codes,
    which it cannot meaningfully judge. This is the text that must be shown instead, for every variant
    (2a/2b/2c) and every id-listing use of the process set.
    """
    p = world["processes"][pid]
    return f"{pid}: {p['source']} -> {p['target']} ({p['statement']})"


def process_descriptions(process_ids: list[str], world: dict) -> list[str]:
    return [process_description(pid, world) for pid in process_ids]


BRIEF_MAX_CHARS = 8000  # eval_v3.py's --brief default; ENGINE_V3_RESULTS.md confirms this was
                        # the size actually used to build the NDA world's system prompt.


def load_world_model(world_file: Path = WORLD_FILE):
    """The same pydantic World the engine's WorldAdapter expects, loaded read-only from the
    already-exported world_nda_v1.json (no engine files touched)."""
    from dialectic_world.world.model import World

    return World.model_validate_json(world_file.read_text(encoding="utf-8"))


def world_brief(world_file: Path = WORLD_FILE, max_chars: int = BRIEF_MAX_CHARS) -> str:
    """The exact text the agent itself saw as its world description: dialectic_world's
    WorldAdapter.brief() (same class, same max_chars=8000 as eval_v3.py used to build the system
    prompt for the "world" arm -- see ENGINE_V3_RESULTS.md, "изложение мира (до 8000 знаков)").
    Variant 2 (2a/2b) asks about this text, not an exhaustive list of all 152 processes, so the
    question matches what the agent actually had access to when it produced its answer -- the
    same condition variant 1 (self-report, `fits`) is already judged against.
    """
    from dialectic_world.adapter.adapter import WorldAdapter

    return WorldAdapter(load_world_model(world_file), max_chars=max_chars).brief()


def brief_process_ids(world_file: Path = WORLD_FILE, max_chars: int = BRIEF_MAX_CHARS) -> list[str]:
    """Unique process ids actually mentioned in the brief (`[id]` markers from Process.line()),
    in order of first appearance. Typically far fewer than all 152 active processes -- the brief
    is a size-limited excerpt (core process chain + top developing/internal processes)."""
    text = world_brief(world_file, max_chars)
    seen: list[str] = []
    for pid in re.findall(r"\[([A-Za-z0-9]+)\]", text):
        if pid not in seen:
            seen.append(pid)
    return seen


def brief_process_descriptions(world_file: Path = WORLD_FILE, max_chars: int = BRIEF_MAX_CHARS) -> dict[str, str]:
    """id -> that process's own formulation (Process.line(): "[id] source -> target: statement"),
    for every process mentioned in the brief. Used to build variant 2c's option set."""
    w = load_world_model(world_file)
    return {pid: w.get(pid).line() for pid in brief_process_ids(world_file, max_chars)}


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
