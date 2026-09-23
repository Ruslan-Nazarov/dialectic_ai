"""Opt-in live regression suite against real providers.

    DIALECTIC_RUN_LIVE=1 python -m pytest tests/live -v

Env: DIALECTIC_LIVE_ACTOR (default gigachat), DIALECTIC_LIVE_REPEATS (default 1),
DIALECTIC_LIVE_CASES (comma-separated case names), DIALECTIC_LIVE_DIR (where traces
and live_report.json go; default: pytest's tmp dir).
"""
import json
import os
from pathlib import Path

import pytest

from tests.live.cases import CASES, run_case

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(os.getenv("DIALECTIC_RUN_LIVE") != "1", reason="Live provider suite is opt-in"),
]

REPEATS = int(os.getenv("DIALECTIC_LIVE_REPEATS", "1"))
SELECTED = {n.strip() for n in os.getenv("DIALECTIC_LIVE_CASES", "").split(",") if n.strip()}
PARAMS = [pytest.param(case, i, id=f"{case.name}-{i}")
          for case in CASES if not SELECTED or case.name in SELECTED
          for i in range(1, REPEATS + 1)]


@pytest.fixture(scope="module")
def live_dir(tmp_path_factory):
    path = Path(os.getenv("DIALECTIC_LIVE_DIR") or tmp_path_factory.mktemp("live"))
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture(scope="module")
def report(live_dir):
    records = []
    yield records
    (live_dir / "live_report.json").write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")


@pytest.mark.asyncio
@pytest.mark.parametrize("case,idx", PARAMS)
async def test_live_case(case, idx, live_dir, report):
    if os.getenv("DIALECTIC_LIVE_ACTOR", "gigachat") == "gigachat" and not os.getenv("GIGACHAT_AUTH_KEY"):
        pytest.skip("GIGACHAT_AUTH_KEY is not configured")
    trace = live_dir / f"{case.name}_{idx}.jsonl"
    run, elapsed = await run_case(case, trace)
    problems = case.check(run)
    report.append({
        "case": case.name, "idx": idx, "status": run.result.status, "stop_reason": run.result.stop_reason,
        "elapsed": elapsed, "clear_path": run.clear_path, "response": run.response[:300],
        "contradictions": len(run.engine.state.get_all_contradictions()),
        "actions": len(run.engine.state.get_all_actions()),
        "facts": case.observe(run), "problems": problems, "trace": str(trace),
    })
    assert not problems, f"{problems} -- trace: {trace}"
