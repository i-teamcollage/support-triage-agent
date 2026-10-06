from datetime import date

import pytest
from tiny_shop import TICKET_DATE, shop

from support_triage_agent.knowledge import find_order_ids, normalize_order_id, render_order
from support_triage_agent.llm import ToolCall


@pytest.mark.parametrize("written", ["HV-204518", "hv-204518", "HV204518", "HV 204518", "#HV-204518", "204518"])
def test_order_numbers_are_read_however_they_are_written(written):
    assert normalize_order_id(written) == "HV-204518"


@pytest.mark.parametrize("written", ["", "HV-2045", "VW4829103746", "p-001", "2045180"])
def test_things_that_are_not_order_numbers(written):
    assert normalize_order_id(written) is None


def test_order_numbers_named_in_a_ticket():
    text = "Hi, my order HV-204518 has not arrived. Also order number 204777, and #205001 please."
    assert find_order_ids(text) == ["HV-204518", "HV-204777", "HV-205001"]


def test_numbers_that_only_look_like_order_numbers_are_ignored():
    text = "Ticket p-001. Tracking VW4829103746. Postcode 3511 AB. Bed 160 x 200. Order HV204518 twice: HV-204518."
    assert find_order_ids(text) == ["HV-204518"]


def test_help_centre_search_returns_whole_articles_best_first():
    session = shop().session(TICKET_DATE)
    text = session.search_help_centre("delivery costs")
    assert text.startswith('Help centre, best matches for "delivery costs":')
    assert "[HC-04] Delivery times and costs (Delivery)" in text
    assert "free for orders over €75" in text
    assert session.retrieved[0] == "HC-04"
    assert session.top_score == session.best_scores["HC-04"] > 0


def test_search_results_are_the_same_every_time():
    first = shop().session(TICKET_DATE).search_help_centre("return refund delivery")
    second = shop().session(TICKET_DATE).search_help_centre("return refund delivery")
    assert first == second


def test_search_without_a_match_says_so_and_retrieves_nothing():
    session = shop().session(TICKET_DATE)
    assert "no article matches" in session.search_help_centre("zebra")
    assert session.retrieved == []
    assert session.top_score == 0.0


def test_retrieved_articles_keep_the_order_they_were_first_seen():
    session = shop().session(TICKET_DATE)
    session.search_help_centre("tracking number")
    session.search_help_centre("delivery costs tracking")
    assert session.retrieved[0] == "HC-05"
    assert set(session.retrieved) >= {"HC-04", "HC-05"}
    assert len(session.retrieved) == len(set(session.retrieved))


def test_past_ticket_search_shows_who_handled_it():
    session = shop().session(TICKET_DATE)
    text = session.search_past_tickets("charged twice")
    assert "[PT-0001] 2026-08-14, handled by billing: Charged twice for one order" in text
    assert "Resolution: Billing checked" in text
    assert session.past_seen == ["PT-0001"]


def test_lookup_order_shows_the_record_as_plain_text():
    session = shop().session(TICKET_DATE)
    text = session.lookup_order("HV-204518")
    assert text.splitlines()[0] == "Order HV-204518"
    assert "Status: shipped" in text
    assert "- 1 x Linen cushion cover, sage (SKU 51207), €19.95 each" in text
    assert "Order total: €108.95" in text
    assert "Veloway Parcel, tracking VW4829103746: shipped on 2026-09-23, expected on 2026-10-02." in text
    assert "Attention" not in text
    assert session.orders_found == {"HV-204518": shop().orders["HV-204518"]}


def test_lookup_accepts_the_order_number_as_the_customer_wrote_it():
    session = shop().session(TICKET_DATE)
    assert session.lookup_order("hv204518").startswith("Order HV-204518")


def test_unknown_order_is_reported_and_remembered():
    session = shop().session(TICKET_DATE)
    assert session.lookup_order("HV-999999") == 'No order found for "HV-999999". Order numbers look like HV-123456.'
    assert session.orders_found == {}
    assert session.failed_lookups == ["HV-999999"]


def test_a_late_parcel_is_flagged_as_of_the_ticket_date():
    text = shop().session(TICKET_DATE).lookup_order("HV-203990")
    assert "Attention (as of 2026-10-01, the date of the ticket):" in text
    assert "- Parcel 1 was expected on 2026-09-18 and has not been delivered." in text


def test_the_same_parcel_is_not_late_before_its_expected_date():
    assert "Attention" not in shop().session(date(2026, 9, 17)).lookup_order("HV-203990")


def test_an_overdue_refund_is_flagged():
    text = shop().session(date(2026, 10, 6)).lookup_order("HV-205001")
    assert "Refund: €49.90, processing, expected by 2026-10-02." in text
    assert "- The refund was expected by 2026-10-02 and has not been issued." in text


def test_delivered_order_shows_its_return_window():
    text = shop().session(TICKET_DATE).lookup_order("HV-204777")
    assert "delivered on 2026-09-20" in text
    assert "Return window: until 2026-10-20" in text


def test_tool_calls_are_dispatched_by_name_and_recorded():
    session = shop().session(TICKET_DATE)
    text = session.run(ToolCall("lookup_order", {"order_id": "HV-204518"}))
    assert text.startswith("Order HV-204518")
    assert session.calls == [{"name": "lookup_order", "arguments": {"order_id": "HV-204518"}}]


def test_arguments_sent_as_a_json_string_still_work():
    session = shop().session(TICKET_DATE)
    assert session.run(ToolCall("search_help_centre", '{"query": "tracking number"}')).startswith("Help centre")


def test_unknown_tool_and_missing_argument_get_a_clear_answer():
    session = shop().session(TICKET_DATE)
    assert session.run(ToolCall("refund_order", {"order_id": "HV-204518"})).startswith('Unknown tool "refund_order"')
    assert "needs a query" in session.run(ToolCall("search_help_centre", {}))


def payment_line(payment, **fields):
    order = {**shop().orders["HV-204518"], "payment": payment, **fields}
    return next(line for line in render_order(order, TICKET_DATE).splitlines() if line.startswith("Payment:"))


def test_a_cancelled_order_shows_when_the_money_went_back():
    payment = {"method": "card", "status": "refunded", "paid_on": "2026-09-02", "refunded_on": "2026-09-03"}
    assert payment_line(payment, status="cancelled") == "Payment: card, paid on 2026-09-02, refunded on 2026-09-03"


def test_pay_in_30_days_before_the_order_ships_has_no_due_date_yet():
    payment = {"method": "Pay in 30 days", "status": "open", "paid_on": None, "due_on": None, "reminders": []}
    assert payment_line(payment, status="packed") == "Payment: Pay in 30 days, due 30 days after the order ships"


def test_pay_in_30_days_shows_the_due_date_and_the_reminders():
    payment = {
        "method": "Pay in 30 days",
        "status": "paid",
        "paid_on": "2026-09-15",
        "due_on": "2026-09-06",
        "reminders": [{"sent_on": "2026-09-13", "fee": "0.00"}, {"sent_on": "2026-09-20", "fee": "5.00"}],
    }
    order = {**shop().orders["HV-204518"], "payment": payment}
    text = render_order(order, TICKET_DATE)
    assert "Payment: Pay in 30 days, due on 2026-09-06, paid on 2026-09-15" in text
    assert "Reminders sent: 2026-09-13 (no fee), 2026-09-20 (€5.00 fee)" in text
