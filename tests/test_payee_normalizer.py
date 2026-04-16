# tests/test_payee_normalizer.py
import re
import pytest

from payee_normalizer import normalize_payee


@pytest.mark.parametrize(
    "raw, must_contain, must_not_contain",
    [
        # Aggregator gateways – we care that the merchant is retained and
        # aggregator tokens are removed.
        ("ZETTLE_*CHILDREN S TOY", ["children"], ["zettle_*", "zettle *"]),
        ("SUMUP *WAFFLE STATION LI", ["waffle"], ["sumup"]),
        ("SQ *BURGER BUZZ", ["burger", "buzz"], ["sq *", "sq *burger"]),
        # Payment to + date suffix should be stripped
        (
            "Payment to SURREY FLOORS & DO 2024-02-09",
            ["surrey", "floors"],
            ["payment to", "2024-02-09"],
        ),
        # ATM withdrawal with date – keep “ATM Withdrawal” or similar,
        # drop the exact date noise at least.
        (
            "ATM Withdrawal SAINSBURYS BANK 2024-04-15",
            ["atm", "withdrawal"],
            ["2024-04-15"],
        ),
        # WWW / domains – strip the WWW / URL noise, keep brand
        ("WWW.MINERVACRAFTS.COM", ["minerva", "craft"], ["www."]),
        # Amazon marketplace short code – reduce to something Amazon-ish
        ("AMZNMktplace", ["amzn", "amazon"], []),
        # Basic shop with extra location junk
        ("MILK AND MORE CAMBERLEY GB", ["milk", "more"], ["camberley", "gb"]),
    ],
)
def test_normalize_payee_basic_properties(raw, must_contain, must_not_contain):
    norm = normalize_payee(raw)

    assert isinstance(norm, str)
    assert norm.strip() != ""

    lower = norm.lower()

    for token in must_contain:
        # any token in the list is acceptable, so skip None/"" tokens
        if token:
            assert token in lower, f"Expected '{token}' in {norm!r} for {raw!r}"

    for token in must_not_contain:
        if token:
            assert token not in lower, f"Did not expect '{token}' in {norm!r} for {raw!r}"


def test_normalize_payee_pirb_maps_to_pirbright_institute():
    raw = "348855063THE PIRB"
    norm = normalize_payee(raw).lower()
    # agreed behaviour: treat PIRB codes as The Pirbright Institute
    assert "pirbright" in norm
    assert re.search(r"\bthe pirb\b", norm) is None  # we want the human name, not the code


def test_normalize_payee_idempotent():
    """Calling normalize_payee twice should not keep changing results."""
    raw = "ZETTLE_*CHILDREN S TOY"
    once = normalize_payee(raw)
    twice = normalize_payee(once)
    assert once == twice