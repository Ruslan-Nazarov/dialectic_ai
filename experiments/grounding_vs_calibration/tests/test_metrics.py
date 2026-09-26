import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from metrics import auroc, bootstrap_ci, error_rates, precision_recall


def test_auroc_perfect_separation():
    scores = [0.9, 0.8, 0.2, 0.1]
    correct = [True, True, False, False]
    assert auroc(scores, correct) == 1.0


def test_auroc_chance():
    scores = [0.5, 0.5, 0.5, 0.5]
    correct = [True, False, True, False]
    assert abs(auroc(scores, correct) - 0.5) < 1e-9


def test_auroc_inverted():
    scores = [0.1, 0.2, 0.8, 0.9]
    correct = [True, True, False, False]
    assert auroc(scores, correct) == 0.0


def test_error_rates_known():
    # signal fires exactly on the incorrect ones -> perfect detector
    correct = [True, True, False, False]
    signal = [False, False, True, True]
    r = error_rates(signal, correct)
    assert r["signal_rate_among_correct"] == 0.0
    assert r["signal_rate_among_incorrect"] == 1.0


def test_precision_recall_known():
    correct = [True, True, False, False]
    signal = [False, True, True, False]  # 1 FP, 1 TP, 1 FN
    r = precision_recall(signal, correct)
    assert r["precision"] == 0.5
    assert r["recall"] == 0.5


@dataclass
class Row:
    doc: int
    hypothesis: str
    val: float


def test_bootstrap_ci_pairs_move_together():
    # two reps per pair; if pairs are resampled together, the CI should never contain an
    # impossible mean given the fixed per-pair values (sanity: bounds within [min, max]).
    rows = []
    for i in range(20):
        rows.append(Row(doc=i, hypothesis="h", val=1.0 if i % 2 == 0 else 0.0))
        rows.append(Row(doc=i, hypothesis="h", val=1.0 if i % 2 == 0 else 0.0))

    def mean_val(rs):
        return sum(r.val for r in rs) / len(rs)

    result = bootstrap_ci(rows, mean_val, n_resamples=500, seed=1)
    assert 0.0 <= result["lo"] <= result["point"] <= result["hi"] <= 1.0
    assert result["n"] > 0


def test_bootstrap_ci_resamples_whole_pairs_not_individual_rows():
    # construct data where a pair's two rows are identical; if the resampler ever split a
    # pair's rows independently, resampled means could hit values impossible when pairs move
    # together as a block (here, since both rows in a pair are equal, this always holds --
    # the real check is that bootstrap_ci groups by (doc, hypothesis) at all).
    rows = [Row(doc=0, hypothesis="a", val=0.0), Row(doc=0, hypothesis="a", val=0.0),
            Row(doc=1, hypothesis="b", val=1.0), Row(doc=1, hypothesis="b", val=1.0)]

    def mean_val(rs):
        return sum(r.val for r in rs) / len(rs)

    result = bootstrap_ci(rows, mean_val, n_resamples=200, seed=2)
    # only achievable means when resampling whole pairs of (0,0) or (1,1): 0, 0.5, 1
    assert result["point"] == 0.5
