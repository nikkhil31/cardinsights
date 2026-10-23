from cardwise.categorize import categorize


def test_known_merchants():
    assert categorize("Swiggy BENGALURU IND") == "Food & Dining"
    assert categorize("Zepto Bengaluru IND") == "Groceries"
    assert categorize("RAZ*MAKEMYTRIP INDIA L Bengaluru IND") == "Travel"
    assert categorize("AMAZON PAY INDIA PRIVA Bangalore IND") == "Shopping"


def test_unknown_goes_other():
    assert categorize("XYZZYUNKNOWNMERCHANT") == "Other"
