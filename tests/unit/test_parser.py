import pytest

from tvscreener_ext.screeners.parser import MTFExpressionParser


def test_parser_basic_mapping():
    assert MTFExpressionParser.parse("1H:TREND > 0") == "TREND_60 > 0"
    assert MTFExpressionParser.parse("4H:RSI < 30") == "RSI_240 < 30"
    assert MTFExpressionParser.parse("1D:MACD > 0") == "MACD_1440 > 0"
    assert MTFExpressionParser.parse("15m:ATR_VALUE > 1.5") == "ATR_VALUE_15 > 1.5"


def test_parser_multiple_expressions():
    expr = "1H:TREND > 0 AND 4H:RSI < 30"
    assert MTFExpressionParser.parse(expr) == "TREND_60 > 0 AND RSI_240 < 30"


def test_parser_keeps_raw_tv_intervals():
    assert MTFExpressionParser.parse("60:TREND > 0") == "TREND_60 > 0"
    assert MTFExpressionParser.parse("1440:RSI < 30") == "RSI_1440 < 30"
    assert MTFExpressionParser.parse("1W:MACD > 0") == "MACD_1W > 0"


def test_parser_unrecognized_timeframe():
    with pytest.raises(ValueError, match="Unrecognized timeframe alias: 'XYZ'"):
        MTFExpressionParser.parse("XYZ:TREND > 0")


def test_parser_word_boundaries():
    # Make sure it doesn't partially match words incorrectly if there are colons in weird places,
    # though the regex should handle it.
    # Note: 'M1H:TREND' shouldn't match as a whole alias '1H' because of \b
    with pytest.raises(ValueError, match="Unrecognized timeframe alias: 'M1H'"):
        MTFExpressionParser.parse("M1H:TREND > 0")
