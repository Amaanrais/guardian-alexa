import pytest

from server import scoring
from server.scoring import Signal


def test_unknown_signal_rejected():
    with pytest.raises(ValueError):
        Signal("made_up", "x")


def test_thresholds():
    assert scoring.link_verdict([]) == "No red flags found"
    assert scoring.link_verdict([Signal("password_field", "a")]) == "No red flags found"
    assert scoring.link_verdict([Signal("otp_field", "a")]) == "Be careful"
    assert scoring.link_verdict([Signal("lookalike_brand", "a")]) == "Don't open this link"


def test_duplicate_codes_count_once():
    s = [Signal("otp_field", "a"), Signal("otp_field", "b")]
    assert scoring.total(s) == scoring.WEIGHTS["otp_field"]


def test_reasons_sorted_by_weight():
    s = [Signal("not_https", "low"), Signal("lookalike_brand", "high")]
    assert scoring.reasons(s) == ["high", "low"]


def test_message_verdict_takes_worst_of_text_and_links():
    assert scoring.message_verdict([], [2]) == "Don't trust this message"
    assert scoring.message_verdict([Signal("gift_card", "g")], [0]) == "Be careful"


def test_no_verdict_says_safe():
    for v in scoring.LINK_VERDICTS + scoring.MESSAGE_VERDICTS:
        assert "safe" not in v.lower()
