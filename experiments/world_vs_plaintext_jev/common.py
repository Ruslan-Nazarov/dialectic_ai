"""Shared helpers for world_vs_plaintext_jev (see PREREGISTRATION.md). Import-only reuse of
../jev_world_and_verifier/jev_batch.py; nothing there is copied or edited."""
from __future__ import annotations

import csv
import json
import re
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = HERE / "data"
CSV_PATH = DATA / "TruthfulQA" / "TruthfulQA.csv"

sys.path.insert(0, str(ROOT / "experiments" / "jev_world_and_verifier"))
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from jev_batch import JevAPIError, call_systemone_with_retry, noul_question  # noqa: E402,F401

NON_ANSWER = re.compile(r"no comment|I don't know|I do not know|not sure", re.I)
JEV_PRICE_PER_MTOK = 0.042  # documented tariff; verified against the TypeSafe console on the pilot

_lock = threading.Lock()


def load_items() -> list[dict]:
    """All TruthfulQA rows minus the 38 whose Best Answer is a refusal. id = 0-based data-row index in the
    CSV (before exclusion), the stable key used everywhere."""
    with open(CSV_PATH, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    items = []
    for i, r in enumerate(rows):
        if NON_ANSWER.search(r["Best Answer"]) or NON_ANSWER.search(r["Best Incorrect Answer"]):
            continue
        items.append({"id": i, "question": r["Question"].strip(), "true": r["Best Answer"].strip(),
                      "false": r["Best Incorrect Answer"].strip(), "type": r["Type"], "category": r["Category"]})
    return items


def jev_noul(question: str, candidate: str, background: str | None = None) -> dict:
    """One Jev call = one question about one candidate answer. Same request in every condition; only the
    optional `background` key of the state differs."""
    state = {"question": question}
    if background is not None:
        state["background"] = background
    q = noul_question(
        {"candidate_answer": candidate,
         "question": "Is the candidate answer a correct answer to the question in the shared state?"},
        criteria={"true": "The candidate answer is factually correct for the question.",
                  "false": "The candidate answer is factually incorrect for the question."},
    )
    res = call_systemone_with_retry(state, {"q": q})
    return {"noul": res.answers["q"]["noul"], "input_tokens": res.input_tokens,
            "output_tokens": res.output_tokens, "request_id": res.request_id, "seconds": round(res.seconds, 2)}


def append_jsonl(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock, open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
