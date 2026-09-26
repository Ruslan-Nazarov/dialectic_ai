import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from retrieval import keyword_search, quote_found_verbatim, split_sentences


def test_quote_found_verbatim_exact():
    text = "The Receiving Party shall not disclose Confidential Information to any third party."
    quote = "The Receiving Party shall not disclose Confidential Information to any third party."
    assert quote_found_verbatim(text, quote)


def test_quote_found_verbatim_whitespace_normalized():
    text = "Line one.\nLine   two continues here."
    quote = "Line one. Line two continues here."
    assert quote_found_verbatim(text, quote)


def test_quote_not_found_when_altered():
    text = "The Receiving Party shall not disclose Confidential Information."
    quote = "The Receiving Party shall disclose Confidential Information."  # 'not' removed
    assert not quote_found_verbatim(text, quote)


def test_keyword_search_ranks_relevant_sentence_first():
    text = (
        "This agreement covers general terms. "
        "The Receiving Party shall not disclose Confidential Information to competitors. "
        "Governing law is the state of Delaware."
    )
    hits = keyword_search(text, "disclose confidential information")
    assert hits
    assert "disclose" in hits[0].lower()


def test_split_sentences_basic():
    sents = split_sentences("First sentence. Second sentence; third clause.")
    assert len(sents) >= 2
