from cardwise.cashback import (channel_for, compute_cashback, is_cashback_credit,
                               is_online, rate_for)


def test_rate_for_online_offline():
    assert rate_for("Groceries", "99", True) == 5.0
    assert rate_for("Groceries", "99", False) == 1.0
    assert rate_for("Fuel", "99", True) == 0.0
    assert rate_for("Subscriptions", "99", False) == 0.0


def test_channel_detection():
    assert is_online("RAZ*Swiggy Online Bangalore IND") is True
    assert is_online("Swiggy BENGALURU IND") is False
    assert channel_for("Swiggy online", "debit") == "online"
    assert channel_for("Swiggy store", "debit") == "offline"
    assert channel_for("CARD CASHBACK", "credit") == "credit"


def test_compute_debit_online():
    assert compute_cashback("Zepto online", "Groceries", "99", 100.0, "debit") == 5.0


def test_compute_debit_offline():
    assert compute_cashback("Zepto store", "Groceries", "99", 100.0, "debit") == 1.0


def test_compute_credit_cashback():
    assert compute_cashback("CARD CASHBACK CREDIT", "Finance & Fees", "99", 50.0, "credit") == 50.0
    assert compute_cashback("PAYMENT RECEIVED", "Finance & Fees", "99", 50.0, "credit") == 0.0


def test_is_cashback_credit():
    assert is_cashback_credit("card cashback")
    assert not is_cashback_credit("payment received")
