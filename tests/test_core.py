"""Deterministic unit tests for the rule-based core (no network, no model).

    python -m pytest -q
"""
from priceiq import analyze
from priceiq.matching import Match
from priceiq.sources import Listing, _num


def _match(competitor, name, price, currency="USD", score=0.9):
    return Match(Listing(competitor, name, price, currency, "http://example/x"), score)


# --- price parsing --------------------------------------------------------
def test_num_parses_currency_symbols():
    assert _num("£51.77") == 51.77
    assert _num("$4.99") == 4.99
    assert _num("1,299.00") == 1299.0


def test_num_returns_none_on_garbage():
    assert _num("out of stock") is None
    assert _num("") is None


# --- MAP violation --------------------------------------------------------
def test_map_violation_flagged_when_competitor_below_floor():
    my = [{"sku": "A", "name": "Widget", "my_price": 10.0, "map_price": 9.0, "currency": "USD"}]
    reports = analyze.analyze(my, {"A": [_match("CheapShop", "Widget clone", 8.0)]})
    r = reports[0]
    assert r.map_violation is True
    assert r.map_details[0][0] == "CheapShop"
    assert r.map_details[0][2] == 8.0


def test_no_map_violation_when_all_above_floor():
    my = [{"sku": "A", "name": "Widget", "my_price": 10.0, "map_price": 9.0, "currency": "USD"}]
    reports = analyze.analyze(my, {"A": [_match("Shop", "Widget", 9.5)]})
    assert reports[0].map_violation is False


# --- pricing position -----------------------------------------------------
def test_position_cheapest():
    my = [{"sku": "A", "name": "W", "my_price": 5.0, "currency": "USD"}]
    reports = analyze.analyze(my, {"A": [_match("S", "W2", 8.0), _match("S", "W3", 9.0)]})
    assert reports[0].position == "cheapest"


def test_position_mid():
    my = [{"sku": "A", "name": "W", "my_price": 8.5, "currency": "USD"}]
    reports = analyze.analyze(my, {"A": [_match("S", "W2", 8.0), _match("S", "W3", 9.0)]})
    assert reports[0].position == "mid"


def test_position_expensive():
    my = [{"sku": "A", "name": "W", "my_price": 20.0, "currency": "USD"}]
    reports = analyze.analyze(my, {"A": [_match("S", "W2", 8.0), _match("S", "W3", 9.0)]})
    assert reports[0].position == "expensive"


def test_position_no_data_without_matches():
    my = [{"sku": "A", "name": "W", "my_price": 20.0, "currency": "USD"}]
    assert analyze.analyze(my, {"A": []})[0].position == "no-data"


# --- report rendering -----------------------------------------------------
def test_format_report_counts_alerts():
    my = [{"sku": "A", "name": "W", "my_price": 10.0, "map_price": 9.0, "currency": "USD"}]
    reports = analyze.analyze(my, {"A": [_match("S", "W2", 8.0)]})
    text = analyze.format_report(reports)
    assert "1 floor-price" in text
    assert "🚨" in text
