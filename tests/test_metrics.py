import math

from support_triage_agent.checks import Failure
from support_triage_agent.metrics import outcome_split, score
from support_triage_agent.pipeline import TicketResult
from support_triage_agent.rules import Hit

DATE_FACT = {"type": "date", "value": "2026-10-02"}
CODE_FACT = {"type": "code", "value": "VW4829103746"}


def label(ticket_id, outcome, team, articles=(), facts=(), kind="delivery_eta", edge=None):
    category = {"close": "routine", "route": "complex", "hold": "edge"}[outcome]
    return {
        "id": ticket_id,
        "received": "2026-10-01",
        "category": category,
        "kind": kind,
        "expected_outcome": outcome,
        "team": team,
        "articles": list(articles),
        "key_facts": list(facts),
        "edge": edge,
    }


def closed(ticket_id, reply, cited):
    return TicketResult(ticket_id, "close", "model", team="logistics", reply=reply, cited=list(cited), seconds=12.0)


def routed(ticket_id, team, decided_by="model"):
    return TicketResult(ticket_id, "route", decided_by, team=team, handover={"summary": "x"}, seconds=9.0)


def held(ticket_id, decided_by="hard rules"):
    hits = [Hit("legal", "lawyer")] if decided_by == "hard rules" else []
    return TicketResult(ticket_id, "hold", decided_by, hold_reason="x", hard_rules=hits)


LABELS = [
    label("t-1", "close", "logistics", ["HC-05", "HC-04"], [DATE_FACT, CODE_FACT]),
    label("t-2", "route", "billing", ["HC-16"], kind="double_charge"),
    label("t-3", "hold", "hold", kind="legal_threat", edge="legal_threat"),
]
GOOD_REPLY = "Your parcel (tracking VW 4829 1037 46) is expected on Friday 2 October."


def test_a_perfect_run_meets_every_target():
    results = {"t-1": closed("t-1", GOOD_REPLY, ["HC-05"]), "t-2": routed("t-2", "billing"), "t-3": held("t-3")}
    measures, details = score(LABELS, results)
    assert measures["wrong_closes"].value == 0
    assert (measures["close_rate"].hits, measures["close_rate"].total) == (1, 3)
    assert measures["routing_accuracy"].value == 1.0
    assert measures["grounded_replies"].value == 1.0
    assert "| close (routine) | 1 | 0 | 0 | 1 |" in details


def test_closing_a_ticket_that_needed_a_person_is_a_wrong_close():
    results = {"t-1": routed("t-1", "logistics"), "t-2": closed("t-2", "We only charged you once.", ["HC-16"])}
    measures, details = score(LABELS[:2], results)
    assert measures["wrong_closes"].value == 1
    assert "- t-2 (double_charge): closed, answer key route to billing" in details


def test_a_routine_ticket_routed_to_its_own_team_is_a_correct_route():
    measures, _ = score(LABELS[:1], {"t-1": routed("t-1", "logistics", decided_by="checks")})
    assert (measures["routing_accuracy"].hits, measures["routing_accuracy"].total) == (1, 1)
    assert measures["close_rate"].value == 0.0


def test_routing_an_edge_case_counts_as_wrong():
    measures, details = score(LABELS[2:], {"t-3": routed("t-3", "logistics")})
    assert (measures["routing_accuracy"].hits, measures["routing_accuracy"].total) == (0, 1)
    assert "- t-3 (legal_threat): routed to logistics, answer key hold" in details


def test_routing_to_the_wrong_team_counts_as_wrong():
    measures, _ = score(LABELS[1:2], {"t-2": routed("t-2", "tech")})
    assert measures["routing_accuracy"].value == 0.0


def test_a_grounded_reply_cites_a_relevant_article_and_states_every_key_fact():
    without_code = "Your parcel is expected on 2 October."
    for reply, cited in ((GOOD_REPLY, ["HC-04"]), (without_code, ["HC-05"]), (GOOD_REPLY, ["HC-11"])):
        measures, _ = score(LABELS[:1], {"t-1": closed("t-1", reply, cited)})
        expected = reply == GOOD_REPLY and cited != ["HC-11"]
        assert measures["grounded_replies"].value == (1.0 if expected else 0.0), (reply, cited)


def test_ungrounded_replies_are_listed_with_what_they_miss():
    _, details = score(LABELS[:1], {"t-1": closed("t-1", "It is expected on 2 October.", ["HC-11"])})
    assert "- t-1 (delivery_eta): cites none of HC-05, HC-04; misses VW4829103746" in details


def test_without_routes_routing_accuracy_is_not_a_number():
    measures, _ = score(LABELS[:1], {"t-1": closed("t-1", GOOD_REPLY, ["HC-05"])})
    assert math.isnan(measures["routing_accuracy"].value)


def test_edge_cases_and_failed_closes_are_explained():
    failed = routed("t-1", "logistics", decided_by="checks")
    failed.failed_checks = [Failure("retrieval", "the best help-centre match scores 1.20, below the threshold of 2.00")]
    _, details = score(LABELS[:1] + LABELS[2:], {"t-1": failed, "t-3": held("t-3")})
    assert '- t-3 (legal_threat): held by the hard rules: legal threat ("lawyer")' in details
    assert "- t-1 (delivery_eta): the best help-centre match scores 1.20, below the threshold of 2.00" in details


def test_the_split_of_outcomes_is_counted():
    results = {"t-1": closed("t-1", GOOD_REPLY, ["HC-05"]), "t-2": routed("t-2", "billing"), "t-3": held("t-3")}
    assert outcome_split(results) == {"close": 1, "route": 1, "hold": 1}


def test_the_report_states_the_split_of_outcomes():
    results = {"t-1": closed("t-1", GOOD_REPLY, ["HC-05"]), "t-2": routed("t-2", "billing"), "t-3": held("t-3")}
    _, details = score(LABELS, results)
    assert "Close / route / hold: 1 / 1 / 1 of 3 tickets (33% / 33% / 33%)." in details
