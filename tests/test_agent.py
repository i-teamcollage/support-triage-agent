import json
from datetime import date

import pytest
from tiny_shop import TICKET_DATE, shop

from support_triage_agent.agent import (
    DECISION_SCHEMA,
    MAX_TOOL_CALLS,
    decide,
    decision_messages,
    gather,
    validate_decision,
)
from support_triage_agent.llm import LLM, InvalidOutput
from support_triage_agent.ollama_tools import TOOLS
from support_triage_agent.ticket import Ticket

TEXT = """From: Bram Visser
Received: 2026-10-01 09:12
Subject: Where is my order?

Hi, my order HV-204518 hasn't arrived yet. When will it come?
Thanks, Bram
"""

TICKET = Ticket.parse("t-001", TEXT)

CLOSE = {
    "outcome": "close",
    "team": "logistics",
    "reply": "Hi Bram, your order HV-204518 is on its way with Veloway Parcel (tracking VW4829103746) and is "
    "expected on 2 October 2026. Hollinvale Home customer service",
    "cited_articles": ["HC-05"],
    "handover": {"summary": "", "customer_wants": "", "agent_found": "", "order_facts": "", "next_step": ""},
    "hold_reason": "",
}


def calls(*pairs):
    return {"tool_calls": [{"name": name, "arguments": arguments} for name, arguments in pairs]}


class ScriptedModel:
    """Stands in for Ollama: answers from a script, one answer per request, and keeps every request."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        answer = self.answers.pop(0)
        if isinstance(answer, dict) and "tool_calls" not in answer:
            answer = {"content": json.dumps(answer)}
        elif isinstance(answer, str):
            answer = {"content": answer}
        return {"content": "", "tool_calls": [], "prompt_tokens": 800, "output_tokens": 40, **answer}


def llm_with(tmp_path, *answers):
    model = ScriptedModel(*answers)
    return LLM(mode="live", runs_root=tmp_path, num_ctx=16384, transport=model), model


def test_a_ticket_knows_when_it_arrived_and_what_it_is_about():
    assert TICKET.received == date(2026, 10, 1)
    assert TICKET.subject == "Where is my order?"
    assert TICKET.sender == "Bram Visser"
    assert TICKET.order_ids == ["HV-204518"]


def test_a_ticket_without_headers_is_dated_today():
    ticket = Ticket.parse("adhoc", "where is HV-204518??", today=date(2026, 10, 3))
    assert ticket.received == date(2026, 10, 3)
    assert ticket.subject == "where is HV-204518??"


def test_gather_runs_the_tools_the_model_asks_for_then_stops(tmp_path):
    llm, model = llm_with(
        tmp_path,
        calls(("lookup_order", {"order_id": "HV-204518"}), ("search_help_centre", {"query": "tracking parcel"})),
        "DONE",
    )
    session = shop().session(TICKET_DATE)
    gather(llm, TICKET, session, label="t-001")
    assert list(session.orders_found) == ["HV-204518"]
    assert "HC-05" in session.retrieved
    assert len(model.requests) == 2
    for request in model.requests:
        assert request["tools"] == TOOLS
        assert "format" not in request
    follow_up = model.requests[1]["messages"]
    assert follow_up[2]["role"] == "assistant"
    assert follow_up[2]["tool_calls"][0] == {
        "function": {"name": "lookup_order", "arguments": {"order_id": "HV-204518"}}
    }
    assert follow_up[3]["role"] == "tool" and follow_up[3]["tool_name"] == "lookup_order"
    assert follow_up[3]["content"].startswith("Order HV-204518")
    assert follow_up[4]["tool_name"] == "search_help_centre"


def test_the_first_request_explains_the_job_and_carries_the_ticket(tmp_path):
    llm, model = llm_with(tmp_path, "DONE", "DONE")
    gather(llm, TICKET, shop().session(TICKET_DATE), label="t-001")
    system, user = model.requests[0]["messages"][:2]
    assert system["role"] == "system" and "at most 4 tool calls" in system["content"]
    assert TEXT.strip() in user["content"]


def test_gather_stops_after_four_tool_calls(tmp_path):
    three = calls(*[("search_help_centre", {"query": f"question {n}"}) for n in range(3)])
    llm, model = llm_with(tmp_path, three, three, three)
    session = shop().session(TICKET_DATE)
    gather(llm, TICKET, session, label="t-001")
    assert MAX_TOOL_CALLS == 4
    assert len(session.calls) == 4
    assert len(model.requests) == 2


def test_a_model_that_stops_without_searching_the_help_centre_is_reminded(tmp_path):
    llm, model = llm_with(
        tmp_path,
        calls(("lookup_order", {"order_id": "HV-204518"})),
        "DONE",
        calls(("search_help_centre", {"query": "tracking parcel"})),
        "DONE",
    )
    session = shop().session(TICKET_DATE)
    gather(llm, TICKET, session, label="t-001")
    assert "HC-05" in session.retrieved
    assert len(model.requests) == 4
    messages = model.requests[2]["messages"]
    assert messages[4] == {"role": "assistant", "content": "DONE"}
    assert messages[5]["role"] == "user" and "not searched the help centre" in messages[5]["content"]


def test_the_reminder_to_search_comes_only_once(tmp_path):
    llm, model = llm_with(tmp_path, "DONE", "DONE")
    session = shop().session(TICKET_DATE)
    gather(llm, TICKET, session, label="t-001")
    assert session.calls == []
    assert len(model.requests) == 2


def test_gather_returns_the_time_the_model_took(tmp_path):
    llm, _ = llm_with(tmp_path, "DONE", "DONE")
    assert gather(llm, TICKET, shop().session(TICKET_DATE), label="t-001") >= 0.0


def test_the_decision_is_a_separate_call_with_a_schema_and_no_tools(tmp_path):
    session = shop().session(TICKET_DATE)
    session.lookup_order("HV-204518")
    session.search_help_centre("tracking parcel")
    llm, model = llm_with(tmp_path, CLOSE)
    reply = decide(llm, TICKET, session, label="t-001")
    assert reply.data == CLOSE
    request = model.requests[0]
    assert request["format"] == DECISION_SCHEMA
    assert "tools" not in request


def test_the_decision_prompt_holds_the_ticket_and_all_the_evidence():
    session = shop().session(TICKET_DATE)
    session.lookup_order("HV-204518")
    session.lookup_order("HV-999999")
    session.search_help_centre("tracking parcel")
    session.search_past_tickets("parcel not arrived")
    system, user = decision_messages(TICKET, session)
    assert "close" in system["content"] and "route" in system["content"] and "hold" in system["content"]
    assert TEXT.strip() in user["content"]
    assert "Order total: €108.95" in user["content"]
    assert 'No order found for "HV-999999"' in user["content"]
    assert "[HC-05] Tracking your parcel (Delivery)" in user["content"]
    assert "[PT-0002]" in user["content"]


def test_the_decision_prompt_asks_for_the_amount_when_the_customer_asks_what_something_costs():
    system, _ = decision_messages(TICKET, shop().session(TICKET_DATE))
    rules = system["content"].split("Rules for a reply (close only):", 1)[1].split("Handover (route only)", 1)[0]
    assert "asks what something costs" in rules
    assert "state the amount from the cited article" in rules


def test_the_decision_prompt_counts_a_planned_order_over_a_limit_as_a_close():
    system, _ = decision_messages(TICKET, shop().session(TICKET_DATE))
    close = system["content"].split("- close:", 1)[1].split("- route:", 1)[0]
    assert "a planned order that is over a limit the help centre gives" in close


def test_the_decision_prompt_says_when_nothing_was_found():
    _, user = decision_messages(TICKET, shop().session(TICKET_DATE))
    assert "Orders looked up: none." in user["content"]
    assert "Help-centre articles: none." in user["content"]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"reply": " "}, "reply"),
        ({"cited_articles": []}, "cited_articles"),
        ({"outcome": "route"}, "handover"),
        ({"outcome": "hold"}, "hold_reason"),
        ({"team": "sales"}, "team"),
    ],
)
def test_an_incomplete_decision_is_rejected_with_the_reason(change, message):
    with pytest.raises(ValueError, match=message):
        validate_decision({**CLOSE, **change})


def test_an_incomplete_decision_gets_one_retry(tmp_path):
    llm, model = llm_with(tmp_path, {**CLOSE, "reply": ""}, CLOSE)
    reply = decide(llm, TICKET, shop().session(TICKET_DATE), label="t-001")
    assert reply.data == CLOSE
    assert "reply" in model.requests[1]["messages"][-1]["content"]


def test_two_unusable_decisions_raise(tmp_path):
    llm, _ = llm_with(tmp_path, "not json", "still not json")
    with pytest.raises(InvalidOutput, match="t-001"):
        decide(llm, TICKET, shop().session(TICKET_DATE), label="t-001")
