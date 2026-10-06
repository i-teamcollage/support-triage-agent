"""Stand-in models for tests. Neither one reads the ticket the way a model would: they answer from the answer key.

PerfectModel looks up the order the ticket names, searches the help centre with the titles of the ticket's
relevant articles, and then decides as the answer key says: a closing reply that states every key fact and
cites the relevant articles it retrieved, a route to the owning team with a handover, or a hold. Run on the
practice split, it measures the ceiling of the deterministic layer: what the hard rules and the checks allow
when the model makes no mistake.

EagerCloser tries to close every ticket, with a reply that names no date or amount and cites the best article
it found for the ticket's subject line. Whatever it closes that should have gone to a person shows a hole in
the safety net: the hard rules and the checks are all that stand in its way.
"""

import json
import re
from pathlib import Path

MONTHS = "January February March April May June July August September October November December".split()


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _ticket_text(request: dict) -> str:
    user = next(message["content"] for message in request["messages"] if message["role"] == "user")
    return user.split("<<<\n", 1)[1].split("\n>>>", 1)[0]


def _retrieved_articles(request: dict) -> list[str]:
    user = next(message["content"] for message in request["messages"] if message["role"] == "user")
    return re.findall(r"^\[(HC-\d{2})\] ", user, re.MULTILINE)


def _answer(content: str = "", calls: list[dict] | None = None) -> dict:
    return {"content": content, "tool_calls": calls or [], "prompt_tokens": 2400, "output_tokens": 180}


def say(fact: dict) -> str:
    """A key fact in plain English, the way a careful agent would write it."""
    if fact["type"] == "date":
        year, month, day = (int(part) for part in fact["value"].split("-"))
        return f"{day} {MONTHS[month - 1]} {year}"
    if fact["type"] == "amount":
        return f"€{float(fact['value']):,.2f}"
    if fact["type"] == "duration":
        return f"{fact['value']} {fact['unit']}"
    return str(fact["value"])


class _StandIn:
    def __init__(self, data_dir: Path, split: str):
        self.labels = {}
        for label in _read_jsonl(data_dir / split / "labels.jsonl"):
            text = (data_dir / split / label["file"]).read_text(encoding="utf-8").strip()
            self.labels[text] = label
        self.articles = {article["id"]: article for article in _read_jsonl(data_dir / "shop" / "help_centre.jsonl")}
        self.calls = 0

    def __call__(self, request: dict) -> dict:
        self.calls += 1
        label = self.labels[_ticket_text(request)]
        if "tools" in request:
            if any(message["role"] == "tool" for message in request["messages"]):
                return _answer("DONE")
            return _answer(calls=self.lookups(label, _ticket_text(request)))
        return _answer(json.dumps(self.decide(label, _retrieved_articles(request)), ensure_ascii=False))

    @staticmethod
    def _blank(team: str) -> dict:
        handover = {"summary": "", "customer_wants": "", "agent_found": "", "order_facts": "", "next_step": ""}
        return {"outcome": "", "team": team, "reply": "", "cited_articles": [], "handover": handover, "hold_reason": ""}


class PerfectModel(_StandIn):
    def lookups(self, label: dict, text: str) -> list[dict]:
        calls = [{"name": "lookup_order", "arguments": {"order_id": label["order_id"]}}] if label["order_id"] else []
        for article_id in label["articles"][:2]:
            calls.append({"name": "search_help_centre", "arguments": {"query": self.articles[article_id]["title"]}})
        return calls

    def decide(self, label: dict, retrieved: list[str]) -> dict:
        team = label["team"] if label["team"] != "hold" else "logistics"
        decision = self._blank(team)
        if label["expected_outcome"] == "close":
            facts = "; ".join(say(fact) for fact in label["key_facts"])
            reply = f"Hello,\n\nThank you for your message. The facts you asked about: {facts}.\n\n"
            reply += "Hollinvale Home customer service"
            cited = [article_id for article_id in label["articles"] if article_id in retrieved] or label["articles"][:1]
            decision.update(outcome="close", reply=reply, cited_articles=cited)
        elif label["expected_outcome"] == "route":
            handover = {
                "summary": f"A {label['kind'].replace('_', ' ')} ticket.",
                "customer_wants": "A person to sort it out.",
                "agent_found": "The order record and the help centre, as shown.",
                "order_facts": label["order_id"] or "",
                "next_step": f"The {label['team']} team takes it from here.",
            }
            decision.update(outcome="route", handover=handover)
        else:
            decision.update(outcome="hold", hold_reason=f"Edge case: {label['kind'].replace('_', ' ')}.")
        return decision


class EagerCloser(_StandIn):
    def lookups(self, label: dict, text: str) -> list[dict]:
        subject = re.search(r"^Subject: (.*)$", text, re.MULTILINE).group(1)
        calls = [{"name": "lookup_order", "arguments": {"order_id": label["order_id"]}}] if label["order_id"] else []
        return calls + [{"name": "search_help_centre", "arguments": {"query": subject}}]

    def decide(self, label: dict, retrieved: list[str]) -> dict:
        decision = self._blank("logistics")
        reply = "Hello,\n\nThank you for your message. We have looked into it and everything is in order.\n\n"
        decision.update(
            outcome="close", reply=reply + "Hollinvale Home customer service", cited_articles=retrieved[:1] or ["HC-01"]
        )
        return decision
