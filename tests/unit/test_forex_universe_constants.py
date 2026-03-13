from tvscreener.constants.forex import DEFAULT_FOREX_PAIRS, FOREX_MAJORS, FOREX_MINORS


def test_forex_majors_are_fixed_and_usd_based() -> None:
    assert FOREX_MAJORS == [
        "EURUSD",
        "GBPUSD",
        "USDJPY",
        "USDCHF",
        "USDCAD",
        "AUDUSD",
        "NZDUSD",
    ]
    assert all("USD" in p for p in FOREX_MAJORS)
    assert len(set(FOREX_MAJORS)) == len(FOREX_MAJORS)


def test_forex_minors_exclude_usd_and_are_unique() -> None:
    assert all("USD" not in p for p in FOREX_MINORS)
    assert len(set(FOREX_MINORS)) == len(FOREX_MINORS)


def test_default_forex_pairs_is_majors_plus_minors() -> None:
    assert DEFAULT_FOREX_PAIRS == FOREX_MAJORS + FOREX_MINORS
