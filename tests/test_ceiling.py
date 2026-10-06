"""The ceiling of the deterministic layer, measured on the practice split only.

The test split is never used here: it is scored once, on the stored run of the real model.
"""

import json
from pathlib import Path

import pytest
from perfect_model import EagerCloser, PerfectModel

from support_triage_agent.checks import RETRIEVAL_THRESHOLD
from support_triage_agent.knowledge import KnowledgeBase
from support_triage_agent.llm import LLM
from support_triage_agent.metrics import score
from support_triage_agent.pipeline import triage
from support_triage_agent.rules import hard_rules
from support_triage_agent.ticket import Ticket

DATA = Path(__file__).resolve().parents[1] / "data"
LABELS = [json.loads(line) for line in (DATA / "practice" / "labels.jsonl").read_text(encoding="utf-8").splitlines()]
KB = KnowledgeBase.from_dir(DATA / "shop")


def ticket(label: dict) -> Ticket:
    return Ticket.parse(label["id"], (DATA / "practice" / label["file"]).read_text(encoding="utf-8"))


def run(model_class, tmp_path):
    model = model_class(DATA, "practice")
    llm = LLM(mode="live", runs_root=tmp_path, num_ctx=16384, transport=model)
    results = {label["id"]: triage(ticket(label), llm, KB) for label in LABELS}
    return results, *score(LABELS, results)


@pytest.fixture(scope="module")
def perfect(tmp_path_factory):
    return run(PerfectModel, tmp_path_factory.mktemp("perfect"))


def test_with_a_model_that_makes_no_mistake_every_routine_ticket_is_closed(perfect):
    results, measures, details = perfect
    assert measures["close_rate"].hits == sum(label["expected_outcome"] == "close" for label in LABELS), details
    assert measures["close_rate"].value == pytest.approx(0.60)


def test_with_a_model_that_makes_no_mistake_every_criterion_is_met(perfect):
    _, measures, details = perfect
    assert measures["wrong_closes"].value == 0, details
    assert measures["routing_accuracy"].value == 1.0, details
    assert measures["grounded_replies"].value == 1.0, details


def test_the_hard_rules_hold_every_edge_case_before_the_model_is_asked(perfect):
    results, _, _ = perfect
    for label in LABELS:
        if label["expected_outcome"] == "hold":
            assert results[label["id"]].decided_by == "hard rules", label["id"]


def test_no_routine_or_complex_ticket_trips_a_hard_rule():
    for label in LABELS:
        if label["expected_outcome"] != "hold":
            assert hard_rules(ticket(label).text) == [], label["id"]


def test_if_the_model_tried_to_close_every_ticket_the_checks_would_stop_every_wrong_close(tmp_path):
    results, measures, details = run(EagerCloser, tmp_path)
    assert measures["wrong_closes"].value == 0, details
    assert measures["close_rate"].hits > 0, "the eager closer must be able to close something, or it tests nothing"


def test_the_retrieval_threshold_was_tuned_on_the_practice_split():
    """Half the weakest score the right article reaches when searched by its title, rounded down to 0.1.

    A model's query is shorter and looser than an article title, so a match half as strong still counts;
    a query made of one common word does not.
    """
    best = []
    for label in LABELS:
        if label["expected_outcome"] == "close":
            [(_, top), *_] = KB.help_index.search(KB.articles[label["articles"][0]]["title"])
            best.append(top)
    assert RETRIEVAL_THRESHOLD == int(min(best) / 2 * 10) / 10
    for word in ("order", "orders", "delivery", "item", "items", "account", "days"):
        assert KB.help_index.search(word)[0][1] < RETRIEVAL_THRESHOLD, word
