"""Score the agent's decisions against the answer key, using the rules in the spec.

- wrong_closes: tickets the agent closed whose expected outcome is route or hold.
- close_rate: tickets closed, over all tickets.
- routing_accuracy: over every ticket the agent routed, the share sent to the owning team in the answer key.
  Edge cases are labelled "hold", so routing one is always wrong.
- grounded_replies: over every closing reply, the share that cites at least one of the ticket's relevant
  articles and states every key fact (dates and amounts normalized before matching).
"""

from __future__ import annotations

import statistics

from .acceptance import Measure, count, rate
from .checks import RETRIEVAL_THRESHOLD
from .facts import describe_fact, fact_stated
from .pipeline import TicketResult
from .rules import describe_hits

OUTCOMES = ("close", "route", "hold")
ROWS = {"close": "close (routine)", "route": "route (complex)", "hold": "hold (edge)"}


def grounding_problems(label: dict, result: TicketResult) -> list[str]:
    """Why a closing reply is not grounded; an empty list means it is."""
    problems = []
    if not any(article_id in label["articles"] for article_id in result.cited):
        problems.append(f"cites none of {', '.join(label['articles']) or 'the relevant articles'}")
    year = int(label["received"][:4])
    missing = [describe_fact(fact) for fact in label["key_facts"] if not fact_stated(fact, result.reply or "", year)]
    if missing:
        problems.append(f"misses {', '.join(missing)}")
    return problems


def _edge_outcome(result: TicketResult) -> str:
    if result.outcome == "hold":
        if result.decided_by == "hard rules":
            return f"held by the hard rules: {describe_hits(result.hard_rules)}"
        if result.decided_by == "unreadable answer":
            return "held, because the model's answer could not be read"
        return "held by the model"
    if result.outcome == "route":
        return f"ROUTED to {result.team} instead of held"
    return "CLOSED instead of held"


def outcome_split(results: dict[str, TicketResult]) -> dict[str, int]:
    return {outcome: sum(result.outcome == outcome for result in results.values()) for outcome in OUTCOMES}


def score(labels: list[dict], results: dict[str, TicketResult]) -> tuple[dict[str, Measure], str]:
    matrix = {expected: dict.fromkeys(OUTCOMES, 0) for expected in OUTCOMES}
    closed = grounded = routed = routed_right = 0
    wrong, misrouted, ungrounded, edges, failed_closes, close_scores = [], [], [], [], [], []

    for label in labels:
        result = results[label["id"]]
        expected = label["expected_outcome"]
        name = f"{label['id']} ({label['kind']})"
        matrix[expected][result.outcome] += 1
        if result.outcome == "close":
            closed += 1
            if expected != "close":
                answer = f"route to {label['team']}" if expected == "route" else "hold"
                wrong.append(f"{name}: closed, answer key {answer}")
            problems = grounding_problems(label, result)
            if problems:
                ungrounded.append(f"{name}: {'; '.join(problems)}")
            else:
                grounded += 1
        elif result.outcome == "route":
            routed += 1
            if result.team == label["team"]:
                routed_right += 1
            else:
                misrouted.append(f"{name}: routed to {result.team}, answer key {label['team']}")
        if label.get("edge"):
            edges.append(f"{name}: {_edge_outcome(result)}")
        if result.decided_by == "checks":
            failed_closes.append(f"{name}: {'; '.join(failure.reason for failure in result.failed_checks)}")
        if result.decided_by == "checks" or (result.outcome == "close" and result.decided_by == "model"):
            close_scores.append(result.top_score)

    measures = {
        "wrong_closes": count(len(wrong)),
        "close_rate": rate(closed, len(labels)),
        "routing_accuracy": rate(routed_right, routed),
        "grounded_replies": rate(grounded, closed),
    }
    sections = {
        "wrong": wrong,
        "misrouted": misrouted,
        "ungrounded": ungrounded,
        "edges": edges,
        "failed_closes": failed_closes,
    }
    return measures, _details(matrix, sections, close_scores)


def _details(matrix: dict[str, dict[str, int]], sections: dict[str, list[str]], close_scores: list[float]) -> str:
    done = [sum(matrix[expected][outcome] for expected in OUTCOMES) for outcome in OUTCOMES]
    total = sum(done)
    shares = " / ".join(f"{count / total * 100:.0f}%" for count in done) if total else "n/a"
    lines = [
        "## Close, route, hold",
        "",
        f"Close / route / hold: {' / '.join(map(str, done))} of {total} tickets ({shares}).",
        "",
        "Rows are the answer key; columns are what the agent did.",
        "",
        "| Answer key | close | route | hold | Total |",
        "|---|---|---|---|---|",
    ]
    for expected, row in matrix.items():
        lines.append(f"| {ROWS[expected]} | {' | '.join(str(row[o]) for o in OUTCOMES)} | {sum(row.values())} |")
    totals = [sum(matrix[e][o] for e in OUTCOMES) for o in OUTCOMES]
    lines.append(f"| Total | {' | '.join(map(str, totals))} | {sum(totals)} |")

    def listing(title: str, items: list[str], empty: str = "None.") -> None:
        lines.extend(["", f"## {title}", ""])
        lines.extend([f"- {item}" for item in items] or [empty])

    listing("Wrong closes", sections["wrong"])
    listing("Routing mistakes", sections["misrouted"])
    listing("Closing replies that are not grounded", sections["ungrounded"])
    listing("Edge cases", sections["edges"], "None in this split.")
    listing("Closes the checks turned into routes", sections["failed_closes"])
    lines.extend(["", "## Help-centre retrieval", ""])
    if close_scores:
        lines.append(
            f"Best help-centre score of the tickets the model wanted to close: lowest {min(close_scores):.2f}, "
            f"median {statistics.median(close_scores):.2f}. A close needs at least {RETRIEVAL_THRESHOLD:.2f}."
        )
    else:
        lines.append("The model wanted to close no ticket.")
    return "\n".join(lines)
