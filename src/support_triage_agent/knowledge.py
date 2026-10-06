"""What the agent can look things up in: the help centre, past tickets and the orders database.

The three tools return plain text with no timestamps and a fixed order, so the same question always
gets the same answer and a stored run replays exactly. A session remembers what was retrieved; the
checks use it to verify the model's reply.
"""

from __future__ import annotations

import json
import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from .llm import ToolCall
from .textsearch import BM25

HELP_RESULTS = 3
PAST_RESULTS = 3
EXAMPLE_ORDER = "HV-123456"

_ORDER_ID = re.compile(r"\bHV[\s-]?(\d{6})\b", re.IGNORECASE)
_ORDER_WORD = re.compile(
    r"\border(?:\s+(?:number|no\.?|nr\.?|id|ref(?:erence)?))?\s*[:#]?\s*#?\s*(\d{6})\b", re.IGNORECASE
)
_HASH_NUMBER = re.compile(r"(?<!\w)#\s?(\d{6})\b")


def normalize_order_id(value: Any) -> str | None:
    """HV-204518 however it was written (hv204518, #HV-204518, 204518); None if it is not an order number."""
    match = re.fullmatch(r"#?\s*(?:HV[\s-]?)?(\d{6})", str(value).strip(), re.IGNORECASE)
    return f"HV-{match.group(1)}" if match else None


def find_order_ids(text: str) -> list[str]:
    """Order numbers the ticket names, in the order they appear."""
    found = []
    for pattern in (_ORDER_ID, _ORDER_WORD, _HASH_NUMBER):
        found += [(match.start(), f"HV-{match.group(1)}") for match in pattern.finditer(text)]
    return list(dict.fromkeys(order_id for _, order_id in sorted(found)))


def money(value: str | Decimal) -> str:
    return f"€{Decimal(value):,.2f}"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class KnowledgeBase:
    def __init__(self, articles: list[dict], past_tickets: list[dict], orders: list[dict]):
        self.articles = {article["id"]: article for article in articles}
        self.past_tickets = {ticket["id"]: ticket for ticket in past_tickets}
        self.orders = {order["order_id"]: order for order in orders}
        self.help_index = BM25({a["id"]: f"{a['title']}\n{a['section']}\n{a['body']}" for a in articles})
        self.past_index = BM25({t["id"]: f"{t['subject']}\n{t['message']}\n{t['resolution']}" for t in past_tickets})

    @classmethod
    def from_dir(cls, directory: str | Path) -> KnowledgeBase:
        folder = Path(directory)
        return cls(
            _read_jsonl(folder / "help_centre.jsonl"),
            _read_jsonl(folder / "past_tickets.jsonl"),
            _read_jsonl(folder / "orders.jsonl"),
        )

    def session(self, today: date) -> Session:
        """A fresh lookup session for one ticket, received on `today`."""
        return Session(self, today)


def _argument(arguments: Any, name: str) -> str:
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except ValueError:
            return arguments.strip()
    if isinstance(arguments, dict):
        value = arguments.get(name)
        if value is None and len(arguments) == 1:
            value = next(iter(arguments.values()))
        return "" if value is None else str(value).strip()
    return ""


class Session:
    """The lookups made for one ticket, and what they returned."""

    def __init__(self, kb: KnowledgeBase, today: date):
        self.kb = kb
        self.today = today
        self.calls: list[dict[str, Any]] = []
        self.retrieved: list[str] = []
        self.best_scores: dict[str, float] = {}
        self.past_seen: list[str] = []
        self.orders_found: dict[str, dict] = {}
        self.failed_lookups: list[str] = []

    @property
    def top_score(self) -> float:
        """The best help-centre match of the session: 0.0 when the help centre was never searched."""
        return max(self.best_scores.values(), default=0.0)

    def run(self, call: ToolCall) -> str:
        self.calls.append({"name": call.name, "arguments": call.arguments})
        if call.name == "search_help_centre":
            return self.search_help_centre(_argument(call.arguments, "query"))
        if call.name == "search_past_tickets":
            return self.search_past_tickets(_argument(call.arguments, "query"))
        if call.name == "lookup_order":
            return self.lookup_order(_argument(call.arguments, "order_id"))
        return f'Unknown tool "{call.name}". The tools are search_help_centre, search_past_tickets and lookup_order.'

    def search_help_centre(self, query: str) -> str:
        if not query:
            return "search_help_centre needs a query: a few words that describe the customer's question."
        results = self.kb.help_index.search(query, k=HELP_RESULTS)
        if not results:
            return f'Help centre: no article matches "{query}". Try other words.'
        blocks = [f'Help centre, best matches for "{query}":']
        for article_id, score in results:
            if article_id not in self.retrieved:
                self.retrieved.append(article_id)
            self.best_scores[article_id] = max(score, self.best_scores.get(article_id, 0.0))
            article = self.kb.articles[article_id]
            blocks.append(f"{article_heading(article)}, score {score:.2f}\n{article['body']}")
        return "\n\n".join(blocks)

    def search_past_tickets(self, query: str) -> str:
        if not query:
            return "search_past_tickets needs a query: a few words that describe the customer's question."
        results = self.kb.past_index.search(query, k=PAST_RESULTS)
        if not results:
            return f'Past tickets: none match "{query}". Try other words.'
        blocks = [f'Past tickets, best matches for "{query}":']
        for ticket_id, _ in results:
            if ticket_id not in self.past_seen:
                self.past_seen.append(ticket_id)
            blocks.append(render_past_ticket(self.kb.past_tickets[ticket_id]))
        return "\n\n".join(blocks)

    def lookup_order(self, written: str) -> str:
        if not written:
            return f"lookup_order needs an order number, for example {EXAMPLE_ORDER}."
        order_id = normalize_order_id(written)
        order = self.kb.orders.get(order_id) if order_id else None
        if order is None:
            if written not in self.failed_lookups:
                self.failed_lookups.append(written)
            return f'No order found for "{written}". Order numbers look like {EXAMPLE_ORDER}.'
        self.orders_found[order_id] = order
        return render_order(order, self.today)


def article_heading(article: dict) -> str:
    return f"[{article['id']}] {article['title']} ({article['section']})"


def render_past_ticket(ticket: dict) -> str:
    return (
        f"[{ticket['id']}] {ticket['date']}, handled by {ticket['handled_by']}: {ticket['subject']}\n"
        f"Customer: {ticket['message']}\n"
        f"Resolution: {ticket['resolution']}"
    )


def _payment_line(payment: dict) -> str:
    method = payment["method"]
    if method == "Pay in 30 days":
        if not payment.get("due_on"):
            line = f"Payment: {method}, due 30 days after the order ships"
        elif payment["status"] == "open":
            line = f"Payment: {method}, open, due on {payment['due_on']}"
        else:
            line = f"Payment: {method}, due on {payment['due_on']}, {payment['status']} on {payment['paid_on']}"
    else:
        line = f"Payment: {method}, paid on {payment['paid_on']}"
        if payment.get("refunded_on"):
            line += f", refunded on {payment['refunded_on']}"
    reminders = payment.get("reminders") or []
    if reminders:
        sent = [
            f"{r['sent_on']} ({'no fee' if Decimal(r['fee']) == 0 else money(r['fee']) + ' fee'})" for r in reminders
        ]
        line += f"\nReminders sent: {', '.join(sent)}"
    return line


def _parcel_lines(parcels: list[dict]) -> list[str]:
    if not parcels:
        return ["Parcels: none yet"]
    lines = ["Parcels:"]
    for number, parcel in enumerate(parcels, start=1):
        head = f"- Parcel {number} of {len(parcels)}, {parcel['carrier']}, tracking {parcel['tracking']}: "
        head += f"shipped on {parcel['shipped_on']}, "
        if parcel.get("delivered_on"):
            head += f"delivered on {parcel['delivered_on']}."
        else:
            head += f"expected on {parcel['expected_on']}"
            if parcel.get("first_expected_on"):
                head += f" (first expected on {parcel['first_expected_on']})"
            head += "."
            if parcel.get("slot"):
                head += f" Delivery slot booked: {parcel['slot']}."
            update = parcel.get("last_update")
            if update:
                head += f" Last update {update['date']}: {update['event']}."
        lines.append(head)
        lines.append(f"  Contains: {', '.join(parcel['items'])}")
    return lines


def _return_lines(order: dict) -> list[str]:
    returned = order.get("return")
    if not returned:
        return ["Return: none"]
    line = f"Return: {', '.join(returned['items'])}; requested on {returned['requested_on']}"
    if returned.get("collection_on"):
        if returned.get("collected_on"):
            line += f", collected by Brookhaul on {returned['collected_on']}"
        else:
            line += f", Brookhaul collection booked for {returned['collection_on']}"
    if returned.get("received_on"):
        line += f", received at our warehouse on {returned['received_on']}"
    lines = [line + "."]
    refund = returned.get("refund")
    if refund:
        if refund["status"] == "issued":
            lines.append(f"Refund: {money(refund['amount'])}, issued on {refund['issued_on']}.")
        else:
            lines.append(f"Refund: {money(refund['amount'])}, processing, expected by {refund['expected_by']}.")
    return lines


def attention(order: dict, today: date) -> list[str]:
    """What is overdue on this order on the day the ticket arrived."""
    notes = []
    for number, parcel in enumerate(order.get("parcels") or [], start=1):
        expected = parcel.get("expected_on")
        if not parcel.get("delivered_on") and expected and date.fromisoformat(expected) < today:
            notes.append(f"Parcel {number} was expected on {expected} and has not been delivered.")
    returned = order.get("return") or {}
    refund = returned.get("refund")
    if refund and refund["status"] == "processing" and date.fromisoformat(refund["expected_by"]) < today:
        notes.append(f"The refund was expected by {refund['expected_by']} and has not been issued.")
    collection = returned.get("collection_on")
    if collection and not returned.get("collected_on") and date.fromisoformat(collection) < today:
        notes.append(f"The Brookhaul collection booked for {collection} has not happened.")
    return notes


def render_order(order: dict, today: date) -> str:
    customer = order["customer"]
    delivery = order["delivery"]
    lines = [
        f"Order {order['order_id']}",
        f"Placed on: {order['placed_on']}",
        f"Customer: {customer['name']}, {customer['city']}, {customer['country']}",
        f"Status: {order['status']}",
        "Items:",
        *[f"- {i['qty']} x {i['name']} (SKU {i['sku']}), {money(i['unit_price'])} each" for i in order["items"]],
        f"Delivery: {delivery['method']}, {money(delivery['cost'])}",
        f"Order total: {money(order['total'])}",
        _payment_line(order["payment"]),
        f"Invoice: emailed on {order['invoice']['emailed_on']}" if order.get("invoice") else "Invoice: not issued yet",
        *_parcel_lines(order.get("parcels") or []),
    ]
    if order.get("return_by"):
        lines.append(f"Return window: until {order['return_by']}")
    elif order["status"] == "cancelled":
        lines.append("Return window: none, the order was cancelled")
    else:
        lines.append("Return window: starts when the whole order is delivered")
    lines += _return_lines(order)
    notes = attention(order, today)
    if notes:
        lines.append(f"Attention (as of {today.isoformat()}, the date of the ticket):")
        lines += [f"- {note}" for note in notes]
    return "\n".join(lines)
