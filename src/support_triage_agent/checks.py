"""The confidence line: a ticket is closed only when the code can verify the reply.

A close is a claim that the help centre and the order record answer the customer. The code checks it:

- citations: every cited article was retrieved in this session;
- grounding: every date and amount in the reply appears in a looked-up order record or a cited article,
  both sides normalized to ISO dates and decimal amounts;
- order_lookup: every order the ticket names was looked up and found;
- retrieval: the best help-centre match of the session clears a threshold;
- rules_agree: the rules see nothing a person has to fix (no problem signal in the ticket, nothing overdue on
  a looked-up order). Rules can stop a close; they never force one.

A close that fails any check becomes a route with a handover, so a person sees it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .facts import find_amounts, find_dates
from .knowledge import Session, attention, normalize_order_id, render_order
from .rules import RULE_LABELS, problem_signals
from .ticket import Ticket

# Tuned on the practice split only: half the weakest BM25 score the right article reaches there when it is
# searched by its title, rounded down. A query made of one common word ("order", "delivery") stays below it.
# tests/test_ceiling.py recomputes it, so a change to the help centre or the practice split asks for a re-tune.
RETRIEVAL_THRESHOLD = 2.1


@dataclass(frozen=True)
class Failure:
    check: str
    reason: str


def normalize_article_id(value: Any) -> str | None:
    match = re.search(r"\bHC[\s-]?(\d{1,2})\b", str(value), re.IGNORECASE)
    return f"HC-{int(match.group(1)):02d}" if match else None


def _citations(cited: list[str], session: Session) -> list[Failure]:
    failures = []
    for written in cited:
        article_id = normalize_article_id(written)
        if article_id is None:
            failures.append(Failure("citations", f'cites "{written}", which is not an article id'))
        elif article_id not in session.retrieved:
            failures.append(Failure("citations", f"cites {article_id}, which was not retrieved"))
    return failures


def _grounding(reply: str, cited: list[str], ticket: Ticket, session: Session) -> list[Failure]:
    sources = [render_order(order, session.today) for order in session.orders_found.values()]
    sources += [session.kb.articles[aid]["body"] for aid in cited if aid in session.kb.articles]
    year = ticket.received.year
    allowed_dates = {value for source in sources for _, value in find_dates(source, year)}
    allowed_amounts = {value for source in sources for _, value in find_amounts(source)}
    failures = []
    for quote, value in find_dates(reply, year):
        if value not in allowed_dates:
            failures.append(
                Failure(
                    "grounding",
                    f"the reply states {quote} ({value.isoformat()}), "
                    "which is not in the order record or a cited article",
                )
            )
    for quote, value in find_amounts(reply):
        if value not in allowed_amounts:
            failures.append(
                Failure("grounding", f"the reply states {quote}, which is not in the order record or a cited article")
            )
    return failures


def _order_lookup(ticket: Ticket, session: Session) -> list[Failure]:
    missing = {normalize_order_id(written) for written in session.failed_lookups}
    failures = []
    for order_id in ticket.order_ids:
        if order_id in session.orders_found:
            continue
        where = "is not in the orders database" if order_id in missing else "was not looked up"
        failures.append(Failure("order_lookup", f"the ticket names {order_id}, which {where}"))
    return failures


def _retrieval(session: Session, threshold: float) -> list[Failure]:
    if not session.best_scores:
        return [Failure("retrieval", "the help centre was not searched")]
    if session.top_score < threshold:
        return [
            Failure(
                "retrieval",
                f"the best help-centre match scores {session.top_score:.2f}, below the threshold of {threshold:.2f}",
            )
        ]
    return []


def _rules_agree(ticket: Ticket, session: Session) -> list[Failure]:
    failures = [
        Failure("rules_agree", f'the rules see a {RULE_LABELS[hit.rule]} ("{hit.phrase}")')
        for hit in problem_signals(ticket.text)
    ]
    for order_id, order in session.orders_found.items():
        failures += [Failure("rules_agree", f"order {order_id}: {note}") for note in attention(order, session.today)]
    return failures


def check_close(
    decision: dict[str, Any], ticket: Ticket, session: Session, threshold: float = RETRIEVAL_THRESHOLD
) -> list[Failure]:
    """Everything that stops this close. An empty list means the reply can go out."""
    cited = [aid for written in decision["cited_articles"] if (aid := normalize_article_id(written))]
    return [
        *_citations(decision["cited_articles"], session),
        *_grounding(decision["reply"], cited, ticket, session),
        *_order_lookup(ticket, session),
        *_retrieval(session, threshold),
        *_rules_agree(ticket, session),
    ]
