"""One ticket from text to decision: hard rules, the tool loop, one decision, then the checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .agent import decide, gather
from .checks import RETRIEVAL_THRESHOLD, Failure, check_close, normalize_article_id
from .knowledge import KnowledgeBase, Session, money
from .llm import LLM, InvalidOutput
from .rules import Hit, describe_hits, hard_rules
from .ticket import Ticket


@dataclass
class TicketResult:
    ticket_id: str
    outcome: str  # "close", "route" or "hold"
    decided_by: str  # "hard rules", "model", "checks" or "unreadable answer"
    team: str | None = None
    reply: str | None = None
    cited: list[str] = field(default_factory=list)
    handover: dict[str, str] | None = None
    hold_reason: str | None = None
    hard_rules: list[Hit] = field(default_factory=list)
    failed_checks: list[Failure] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    retrieved: list[str] = field(default_factory=list)
    top_score: float = 0.0
    seconds: float = 0.0
    error: str | None = None


def order_summary(order_id: str, order: dict) -> str:
    parts = [f"{order_id}: {order['status']}, total {money(order['total'])}"]
    for number, parcel in enumerate(order.get("parcels") or [], start=1):
        if parcel.get("delivered_on"):
            parts.append(f"parcel {number} delivered on {parcel['delivered_on']}")
        else:
            parts.append(f"parcel {number} expected on {parcel['expected_on']}")
    refund = (order.get("return") or {}).get("refund")
    if refund:
        when = refund.get("issued_on") or refund.get("expected_by")
        parts.append(f"refund {money(refund['amount'])} {refund['status']} ({when})")
    return "; ".join(parts)


def _failed_close_handover(ticket: Ticket, session: Session, decision: dict, failures: list[Failure]) -> dict:
    more = len(failures) - 1
    summary = f"A closing reply was drafted but held back: {failures[0].reason}"
    if more:
        summary += f" (and {more} more problem{'s' if more > 1 else ''})"
    if session.retrieved:
        cited = ", ".join(normalize_article_id(c) or c for c in decision["cited_articles"]) or "nothing"
        found = f"Help-centre articles retrieved: {', '.join(session.retrieved)}. The draft cites {cited}."
    else:
        found = "The help centre was not searched."
    flagged = [failure.reason for failure in failures if failure.check == "rules_agree"]
    if flagged:
        next_step = f"The rules flagged something a person has to handle: {'; '.join(flagged)}. Deal with it first."
    else:
        next_step = "Check the draft reply against the order record and the help centre, correct it, and send it."
    return {
        "summary": f"{summary}.",
        "customer_wants": ticket.subject,
        "agent_found": found,
        "order_facts": " | ".join(order_summary(oid, order) for oid, order in session.orders_found.items()),
        "next_step": f"{next_step}\n\nDraft reply:\n{decision['reply']}",
    }


def triage(ticket: Ticket, llm: LLM, kb: KnowledgeBase, threshold: float = RETRIEVAL_THRESHOLD) -> TicketResult:
    hits = hard_rules(ticket.text)
    if hits:
        reason = f"Hard rule: {describe_hits(hits)}. The model was not asked."
        return TicketResult(ticket.id, "hold", "hard rules", hold_reason=reason, hard_rules=hits)

    session = kb.session(ticket.received)
    seconds = gather(llm, ticket, session, label=ticket.id)

    def looked_up(**fields: Any) -> dict[str, Any]:
        return {
            "tool_calls": session.calls,
            "retrieved": session.retrieved,
            "top_score": session.top_score,
            "seconds": round(seconds, 3),
            **fields,
        }

    try:
        reply = decide(llm, ticket, session, label=ticket.id)
    except InvalidOutput as error:
        reason = "The model's answer could not be read, even after a retry."
        return TicketResult(ticket.id, "hold", "unreadable answer", hold_reason=reason, **looked_up(error=str(error)))
    seconds += reply.seconds
    decision = reply.data

    if decision["outcome"] == "close":
        cited = [aid for written in decision["cited_articles"] if (aid := normalize_article_id(written))]
        failures = check_close(decision, ticket, session, threshold)
        if not failures:
            return TicketResult(
                ticket.id, "close", "model", team=decision["team"], reply=decision["reply"], cited=cited, **looked_up()
            )
        return TicketResult(
            ticket.id,
            "route",
            "checks",
            team=decision["team"],
            reply=decision["reply"],
            cited=cited,
            handover=_failed_close_handover(ticket, session, decision, failures),
            failed_checks=failures,
            **looked_up(),
        )
    if decision["outcome"] == "route":
        return TicketResult(
            ticket.id, "route", "model", team=decision["team"], handover=decision["handover"], **looked_up()
        )
    return TicketResult(ticket.id, "hold", "model", hold_reason=decision["hold_reason"], **looked_up())
