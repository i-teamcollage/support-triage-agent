from datetime import date
from decimal import Decimal

from support_triage_agent.facts import describe_fact, fact_stated, find_amounts, find_dates

OCT_7 = date(2026, 10, 7)


def dates(text, year=None):
    return [value for _, value in find_dates(text, year)]


def amounts(text):
    return [value for _, value in find_amounts(text)]


def test_iso_dates_as_in_the_order_record():
    assert find_dates("Expected delivery: 2026-10-07") == [("2026-10-07", OCT_7)]


def test_english_dates_in_words():
    assert dates("It should arrive on 7 October 2026.") == [OCT_7]
    assert dates("on the 7th October 2026") == [OCT_7]
    assert dates("on October 7, 2026") == [OCT_7]
    assert dates("on Wednesday, 7 October 2026") == [OCT_7]
    assert dates("by 7 Oct 2026") == [OCT_7]
    assert dates("by Oct. 7th, 2026") == [OCT_7]


def test_dates_without_a_year_take_the_year_of_the_ticket():
    assert dates("arrives on 7 October", year=2026) == [OCT_7]
    assert dates("arrives on October 7th", year=2026) == [OCT_7]


def test_dates_without_a_year_are_ignored_when_no_year_is_known():
    assert dates("arrives on 7 October") == []


def test_numeric_dates_are_day_first_as_in_europe():
    assert dates("due on 07/10/2026") == [OCT_7]
    assert dates("due on 7.10.2026") == [OCT_7]


def test_impossible_dates_are_ignored():
    assert dates("31 September 2026") == []


def test_numbers_that_are_not_dates():
    text = "3 to 5 working days, order HV-204518, tracking VW4829103746, before 14:00, bed 160 x 200, 2 x cushion"
    assert dates(text, year=2026) == []


def test_a_month_and_year_alone_is_not_a_date():
    assert dates("since October 2026", year=2026) == []


def test_several_dates_in_reading_order():
    text = "shipped on 2026-09-23 and expected on 26 September"
    assert dates(text, year=2026) == [date(2026, 9, 23), date(2026, 9, 26)]


def test_amounts_with_a_euro_sign_or_code():
    assert amounts("It costs €49.90.") == [Decimal("49.90")]
    assert amounts("It costs € 49.90") == [Decimal("49.90")]
    assert amounts("It costs 49.90 €") == [Decimal("49.90")]
    assert amounts("EUR 49.90 in total") == [Decimal("49.90")]
    assert amounts("49,90 € in total") == [Decimal("49.90")]
    assert amounts("39 euros per order") == [Decimal("39.00")]
    assert amounts("free over €75.") == [Decimal("75.00")]


def test_thousands_separators():
    assert amounts("up to €1,500") == [Decimal("1500.00")]
    assert amounts("€1,149.00") == [Decimal("1149.00")]
    assert amounts("1.149,00 €") == [Decimal("1149.00")]


def test_numbers_without_a_currency_are_not_amounts():
    assert amounts("10% off, bed 160 x 200, 2 x cushion, order 204518") == []


def test_amounts_keep_their_quote():
    assert find_amounts("a refund of €49.90 is on its way") == [("€49.90", Decimal("49.90"))]


def test_date_fact_matches_any_way_of_writing_the_date():
    fact = {"type": "date", "value": "2026-10-07"}
    assert fact_stated(fact, "It is expected on Wednesday 7 October.", year=2026)
    assert fact_stated(fact, "Expected: 2026-10-07", year=2026)
    assert not fact_stated(fact, "It is expected on 8 October.", year=2026)


def test_amount_fact_matches_the_decimal_value():
    fact = {"type": "amount", "value": "39.00"}
    assert fact_stated(fact, "Two-person delivery costs €39 per order.")
    assert fact_stated(fact, "Two-person delivery costs 39,00 €.")
    assert not fact_stated(fact, "Two-person delivery costs €49.00.")


def test_duration_fact_accepts_common_spellings():
    fact = {"type": "duration", "value": 30, "unit": "days"}
    assert fact_stated(fact, "You can return it within 30 days of delivery.")
    assert fact_stated(fact, "We offer a 30-day return window.")
    assert fact_stated(fact, "You have thirty days.")
    assert not fact_stated(fact, "You have 130 days.")
    assert not fact_stated(fact, "You have 30 minutes.")


def test_duration_fact_allows_working_days_and_singular_units():
    assert fact_stated({"type": "duration", "value": 5, "unit": "days"}, "within 5 working days")
    assert fact_stated({"type": "duration", "value": 30, "unit": "minutes"}, "locked for 30 minutes")
    assert fact_stated({"type": "duration", "value": 5, "unit": "years"}, "a 5-year guarantee")
    assert fact_stated({"type": "duration", "value": 2, "unit": "years"}, "a two-year guarantee")


def test_code_fact_ignores_spaces_and_case():
    fact = {"type": "code", "value": "VW4829103746"}
    assert fact_stated(fact, "Your tracking number is vw 4829 1037 46.")
    assert not fact_stated(fact, "Your tracking number is VW4829103747.")


def test_facts_are_described_in_plain_words():
    assert describe_fact({"type": "date", "value": "2026-10-07"}) == "the date 2026-10-07"
    assert describe_fact({"type": "amount", "value": "39.00"}) == "the amount €39.00"
    assert describe_fact({"type": "duration", "value": 30, "unit": "days"}) == "30 days"
    assert describe_fact({"type": "code", "value": "VW4829103746"}) == "VW4829103746"
