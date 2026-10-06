from test_agent import CLOSE, TEXT, TICKET
from tiny_shop import TICKET_DATE, shop

from support_triage_agent.checks import RETRIEVAL_THRESHOLD, check_close, normalize_article_id
from support_triage_agent.ticket import Ticket


def session_with(*queries, orders=("HV-204518",), day=TICKET_DATE):
    session = shop().session(day)
    for order_id in orders:
        session.lookup_order(order_id)
    for query in queries:
        session.search_help_centre(query)
    return session


def failures(decision=CLOSE, ticket=TICKET, session=None, threshold=1.0):
    session = session or session_with("tracking parcel")
    return [(failure.check, failure.reason) for failure in check_close(decision, ticket, session, threshold)]


def checks_failed(**kwargs):
    return [check for check, _ in failures(**kwargs)]


def test_a_proven_close_passes_every_check():
    assert failures() == []


def test_article_ids_are_read_however_they_are_written():
    assert normalize_article_id("hc-5") == "HC-05"
    assert normalize_article_id("[HC-05]") == "HC-05"
    assert normalize_article_id("HC05") == "HC-05"
    assert normalize_article_id("the delivery article") is None
    assert failures(decision={**CLOSE, "cited_articles": ["hc-5"]}) == []


def test_citing_an_article_that_was_not_retrieved_fails():
    assert failures(decision={**CLOSE, "cited_articles": ["HC-05", "HC-11"]}) == [
        ("citations", "cites HC-11, which was not retrieved")
    ]


def test_citing_a_retrieved_past_ticket_next_to_an_article_passes():
    session = session_with("tracking parcel")
    session.search_past_tickets("parcel arrived")
    assert "PT-0002" in session.past_seen
    assert failures(decision={**CLOSE, "cited_articles": ["HC-05", "PT-0002"]}, session=session) == []


def test_citing_only_past_tickets_fails():
    session = session_with("tracking parcel")
    session.search_past_tickets("parcel arrived")
    assert ("citations", "cites no help-centre article") in failures(
        decision={**CLOSE, "cited_articles": ["PT-0002"]}, session=session
    )


def test_citing_a_past_ticket_that_was_not_retrieved_fails():
    assert ("citations", "cites PT-0001, which was not retrieved") in failures(
        decision={**CLOSE, "cited_articles": ["HC-05", "PT-0001"]}
    )


def test_citing_something_that_is_not_an_article_fails():
    assert checks_failed(decision={**CLOSE, "cited_articles": ["delivery article"]}) == ["citations"]


def test_a_date_that_is_not_in_the_order_record_fails():
    reply = "Your order is expected on 5 October 2026."
    assert failures(decision={**CLOSE, "reply": reply}) == [
        (
            "grounding",
            "the reply states 5 October 2026 (2026-10-05), which is not in the order record or a cited article",
        )
    ]


def test_the_order_record_date_written_another_way_passes():
    for reply in ("It should arrive on 2 October.", "Expected delivery: 02/10/2026.", "It ships on 2026-09-23."):
        assert failures(decision={**CLOSE, "reply": reply}) == [], reply


def test_an_amount_from_the_order_record_passes():
    assert failures(decision={**CLOSE, "reply": "Your order total was €108.95."}) == []


def test_an_amount_must_come_from_a_cited_article():
    session = session_with("delivery costs tracking parcel")
    reply = "Standard delivery is free for orders over €75."
    assert failures(decision={**CLOSE, "reply": reply, "cited_articles": ["HC-04"]}, session=session) == []
    assert failures(decision={**CLOSE, "reply": reply, "cited_articles": ["HC-05"]}, session=session) == [
        ("grounding", "the reply states €75, which is not in the order record or a cited article")
    ]


def test_an_order_the_ticket_names_must_have_been_looked_up():
    session = session_with("tracking parcel", orders=())
    decision = {**CLOSE, "reply": "Your order is on its way. The tracking number is in your shipping email."}
    assert failures(decision=decision, session=session) == [
        ("order_lookup", "the ticket names HV-204518, which was not looked up")
    ]


def test_an_order_that_does_not_exist_cannot_back_a_reply():
    ticket = Ticket.parse("t-002", TEXT.replace("HV-204518", "HV-999999"))
    session = session_with("tracking parcel", orders=("HV-999999",))
    assert ("order_lookup", "the ticket names HV-999999, which is not in the orders database") in failures(
        ticket=ticket, session=session
    )


def test_a_weak_help_centre_match_fails():
    session = session_with("tracking parcel")
    score = session.top_score
    assert failures(session=session, threshold=score + 0.01) == [
        ("retrieval", f"the best help-centre match scores {score:.2f}, below the threshold of {score + 0.01:.2f}")
    ]


def test_a_close_without_any_help_centre_search_fails():
    reasons = failures(session=session_with(), decision={**CLOSE, "cited_articles": ["HC-05"]})
    assert ("retrieval", "the help centre was not searched") in reasons


def test_the_threshold_was_set_for_this_help_centre():
    assert 0 < RETRIEVAL_THRESHOLD < 10


def test_a_problem_signal_in_the_ticket_stops_a_close():
    ticket = Ticket.parse("t-003", TEXT.replace("hasn't arrived yet", "arrived cracked"))
    assert failures(ticket=ticket) == [("rules_agree", 'the rules see a delivery or product problem ("cracked")')]


def test_an_overdue_order_stops_a_close():
    ticket = Ticket.parse("t-004", TEXT.replace("HV-204518", "HV-203990"))
    session = session_with("tracking parcel", orders=("HV-203990",))
    reply = "Your order is expected on 18 September."
    assert failures(ticket=ticket, session=session, decision={**CLOSE, "reply": reply}) == [
        ("rules_agree", "order HV-203990: Parcel 1 was expected on 2026-09-18 and has not been delivered.")
    ]


def test_several_problems_are_all_reported_in_a_fixed_order():
    session = session_with(orders=())
    decision = {**CLOSE, "reply": "It arrives on 9 October 2026.", "cited_articles": ["HC-11"]}
    assert checks_failed(decision=decision, session=session) == ["citations", "grounding", "order_lookup", "retrieval"]
