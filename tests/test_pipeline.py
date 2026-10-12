from test_agent import CLOSE, TEXT, TICKET, ScriptedModel, calls
from tiny_shop import shop

from support_triage_agent.llm import LLM
from support_triage_agent.pipeline import triage
from support_triage_agent.ticket import Ticket

LOOKUPS = calls(("lookup_order", {"order_id": "HV-204518"}), ("search_help_centre", {"query": "tracking parcel"}))
ROUTE = {
    **CLOSE,
    "outcome": "route",
    "reply": "",
    "cited_articles": [],
    "handover": {
        "summary": "Parcel late.",
        "customer_wants": "Their parcel.",
        "agent_found": "Shipped, no update.",
        "order_facts": "HV-204518, shipped on 2026-09-23",
        "next_step": "Open a carrier investigation.",
    },
}


def run(tmp_path, *answers, ticket=TICKET, threshold=1.0):
    model = ScriptedModel(*answers)
    llm = LLM(mode="live", runs_root=tmp_path, num_ctx=16384, transport=model)
    return triage(ticket, llm, shop(), threshold=threshold), model


def test_a_hard_rule_holds_the_ticket_without_asking_the_model(tmp_path):
    ticket = Ticket.parse("t-009", TEXT.replace("Thanks", "If not, my lawyer will be in touch. Thanks"))
    result, model = run(tmp_path, ticket=ticket)
    assert result.outcome == "hold"
    assert result.decided_by == "hard rules"
    assert result.hold_reason == 'Hard rule: legal threat ("lawyer"). The model was not asked.'
    assert model.requests == []


def test_a_proven_close_is_closed(tmp_path):
    result, model = run(tmp_path, LOOKUPS, "DONE", CLOSE)
    assert result.outcome == "close"
    assert result.decided_by == "model"
    assert result.reply == CLOSE["reply"]
    assert result.cited == ["HC-05"]
    assert [call["name"] for call in result.tool_calls] == ["lookup_order", "search_help_centre"]
    assert result.failed_checks == []
    assert len(model.requests) == 3


def test_a_close_that_fails_a_check_gets_one_repair_and_is_closed_when_fixed(tmp_path):
    wrong_date = {**CLOSE, "reply": "Your order arrives on 5 October 2026. Hollinvale Home customer service"}
    result, model = run(tmp_path, LOOKUPS, "DONE", wrong_date, CLOSE)
    assert result.outcome == "close"
    assert result.decided_by == "model after repair"
    assert result.reply == CLOSE["reply"]
    assert "5 October 2026" in model.requests[-1]["messages"][-1]["content"]


def test_a_repair_that_chooses_route_is_routed_by_the_model(tmp_path):
    wrong_date = {**CLOSE, "reply": "Your order arrives on 5 October 2026. Hollinvale Home customer service"}
    result, _ = run(tmp_path, LOOKUPS, "DONE", wrong_date, ROUTE)
    assert result.outcome == "route"
    assert result.decided_by == "model"
    assert result.handover == ROUTE["handover"]


def test_a_close_that_fails_a_check_twice_is_routed_with_a_handover(tmp_path):
    wrong_date = {**CLOSE, "reply": "Your order arrives on 5 October 2026. Hollinvale Home customer service"}
    result, _ = run(tmp_path, LOOKUPS, "DONE", wrong_date, wrong_date)
    assert result.outcome == "route"
    assert result.decided_by == "checks"
    assert result.team == "logistics"
    assert [failure.check for failure in result.failed_checks] == ["grounding"]
    handover = result.handover
    assert handover["summary"].startswith("A closing reply was drafted but held back: the reply states 5 October 2026")
    assert handover["customer_wants"] == "Where is my order?"
    assert "HC-05" in handover["agent_found"]
    assert handover["order_facts"].startswith("HV-204518: shipped, total €108.95")
    assert handover["next_step"].endswith(wrong_date["reply"])


def test_a_close_the_rules_disagree_with_asks_a_person_to_fix_the_problem(tmp_path):
    ticket = Ticket.parse("t-010", TEXT.replace("hasn't arrived yet", "was charged twice"))
    result, _ = run(tmp_path, LOOKUPS, "DONE", CLOSE, ticket=ticket)
    assert result.outcome == "route"
    assert result.handover["next_step"].startswith("The rules flagged something a person has to handle: the rules see")


def test_a_route_keeps_the_model_handover(tmp_path):
    result, _ = run(tmp_path, LOOKUPS, "DONE", ROUTE)
    assert (result.outcome, result.decided_by, result.team) == ("route", "model", "logistics")
    assert result.handover == ROUTE["handover"]


def test_the_model_can_hold_a_ticket_too(tmp_path):
    hold = {**ROUTE, "outcome": "hold", "hold_reason": "The customer mentions an injury."}
    result, _ = run(tmp_path, "DONE", "DONE", hold)
    assert (result.outcome, result.decided_by, result.hold_reason) == (
        "hold",
        "model",
        "The customer mentions an injury.",
    )


def test_an_unreadable_decision_goes_to_a_person(tmp_path):
    result, _ = run(tmp_path, "DONE", "DONE", "not json", "{}")
    assert (result.outcome, result.decided_by) == ("hold", "unreadable answer")
    assert result.error is not None
