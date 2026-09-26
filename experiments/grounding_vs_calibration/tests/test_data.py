import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from data import GOLD_FILE, load_world_answers, sanity_check_accuracy

pytestmark = pytest.mark.skipif(
    not GOLD_FILE.exists(),
    reason="ContractNLI not downloaded -- run download_contract_nli.py first",
)


def test_real_data_loads_258_rows_and_reconciles_with_reported_accuracy():
    answers = load_world_answers()
    assert len(answers) == 258
    pairs = {(a.doc, a.hypothesis) for a in answers}
    assert len(pairs) == 129
    acc = sanity_check_accuracy(answers)
    # eval_v3.md reports 54% for the world arm, ALL row; recomputed value must round to it.
    assert round(acc * 100) == 54
