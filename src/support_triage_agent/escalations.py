"""The decision log, and next-day escalation scoring against the answer key.

Every decision is appended to logs/decisions.jsonl. An escalation (a route or a hold) is necessary when the
answer key also sends the ticket to a person, and unnecessary when the answer key expects a close. The most
common unnecessary escalations show where the agent is too careful. Reported without a threshold.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .pipeline import TicketResult

CHECK_CAUSES = {
    "citations": "it cited an article it had not retrieved",
    "grounding": "a date or amount was not in the order record or a cited article",
    "order_lookup": "the order the ticket names was not looked up",
    "retrieval": "the help-centre match was below the threshold",
    "rules_agree": "the rules flagged a problem for a person",
}


def decision_record(result: TicketResult, *, split: str, mode: str, model: str, logged_at: str) -> dict[str, Any]:
    entry = asdict(result)
    entry["hard_rules"] = [{"rule": hit.rule, "phrase": hit.phrase} for hit in result.hard_rules]
    entry["failed_checks"] = [{"check": f.check, "reason": f.reason} for f in result.failed_checks]
    return {"logged_at": logged_at, "split": split, "mode": mode, "model": model, **entry}


def append_decisions(path: str | Path, records: list[dict[str, Any]]) -> None:
    log = Path(path)
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as handle:
        for entry in records:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_decisions(path: str | Path, split: str) -> dict[str, dict[str, Any]]:
    """The latest logged decision for each ticket of the split."""
    log = Path(path)
    if not log.exists():
        return {}
    latest = {}
    for line in log.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entry = json.loads(line)
            if entry["split"] == split:
                latest[entry["ticket_id"]] = entry
    return latest


@dataclass
class EscalationScore:
    escalated: int = 0
    necessary: int = 0
    unnecessary: int = 0
    causes: list[tuple[str, list[str]]] = field(default_factory=list)


def _cause(entry: dict[str, Any], label: dict) -> str:
    decided_by = entry["decided_by"]
    if decided_by == "checks":
        return f"a close held back: {CHECK_CAUSES[entry['failed_checks'][0]['check']]}"
    if decided_by == "hard rules":
        return f"a hard rule fired on a routine question ({entry['hard_rules'][0]['rule']})"
    if decided_by == "unreadable answer":
        return "the model's answer could not be read"
    verb = "routed" if entry["outcome"] == "route" else "held"
    return f"the model {verb} a routine question ({label['kind']})"


def score_escalations(labels: list[dict], decisions: dict[str, dict[str, Any]]) -> EscalationScore:
    score = EscalationScore()
    by_cause: dict[str, list[str]] = {}
    for label in labels:
        entry = decisions.get(label["id"])
        if entry is None or entry["outcome"] == "close":
            continue
        score.escalated += 1
        if label["expected_outcome"] in ("route", "hold"):
            score.necessary += 1
        else:
            score.unnecessary += 1
            by_cause.setdefault(_cause(entry, label), []).append(label["id"])
    score.causes = sorted(by_cause.items(), key=lambda item: (-len(item[1]), item[0]))
    return score


def escalation_report(score: EscalationScore, split: str, tickets: int | None = None) -> str:
    out_of = f" of {tickets} tickets" if tickets is not None else ""
    lines = [
        f"Escalations on the {split} split (the latest decision per ticket in logs/decisions.jsonl): "
        f"{score.escalated}{out_of}",
        f"  necessary   {score.necessary:>3}  the answer key also sends them to a person",
        f"  unnecessary {score.unnecessary:>3}  the answer key expects a closing reply",
        "",
    ]
    if not score.causes:
        lines.append("No unnecessary escalations.")
        return "\n".join(lines)
    lines.append("Most common unnecessary escalations:")
    lines += [f"  {len(ids)}  {cause}: {', '.join(ids)}" for cause, ids in score.causes]
    return "\n".join(lines)
