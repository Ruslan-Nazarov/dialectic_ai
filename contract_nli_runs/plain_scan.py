"""Plain model (one call, no engine) on every test pair whose gold label is Contradiction; lists where it fails.

    python live_runs/contract_nli/plain_scan.py
"""
import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
load_dotenv(ROOT / ".env")

from run_one import TASK, verdict  # noqa: E402
from tests.live.cases import build_actor  # noqa: E402

HERE = Path(__file__).resolve().parent


async def main():
    data = json.loads((HERE / "contract-nli" / "test.json").read_text(encoding="utf-8"))
    pairs = [(doc, key) for doc in data["documents"]
             for key, a in doc["annotation_sets"][0]["annotations"].items() if a["choice"] == "Contradiction"]
    llm = build_actor()
    gate = asyncio.Semaphore(8)
    results = []

    async def one(doc, key):
        task = TASK.format(text=doc["text"].strip(), hypothesis=data["labels"][key]["hypothesis"])
        async with gate:
            try:
                answer = await llm.generate([{"role": "user", "content": task + "\nReturn only JSON: {\"answer\": \"...\"}"}])
            except Exception as exc:
                answer = f"ERROR {type(exc).__name__}: {exc}"
        results.append({"doc": doc["id"], "hypothesis": key, "chars": len(doc["text"]), "verdict": verdict(answer),
                        "answer": answer[:600]})

    await asyncio.gather(*(one(d, k) for d, k in pairs))
    results.sort(key=lambda r: (r["verdict"] == "Contradiction", r["chars"]))
    (HERE / "plain_scan.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    wrong = [r for r in results if r["verdict"] != "Contradiction"]
    print(f"{len(results)} pairs with gold Contradiction; plain model wrong on {len(wrong)}")
    by = {}
    for r in wrong:
        by.setdefault(r["hypothesis"], []).append(r["verdict"])
    for key, verdicts in sorted(by.items(), key=lambda kv: -len(kv[1])):
        print(f"  {key}: {len(verdicts)} wrong ({', '.join(sorted(set(verdicts)))})")
    for r in wrong[:8]:
        print(f"  doc {r['doc']} {r['hypothesis']} ({r['chars']} chars) -> {r['verdict']}")


asyncio.run(main())
