import json

from test_metrics import LABELS, closed, held, label, routed

from support_triage_agent.checks import Failure
from support_triage_agent.escalations import (
    append_decisions,
    decision_record,
    escalation_report,
    read_decisions,
    score_escalations,
)


def record(result, split="test"):
    return decision_record(result, split=split, mode="replay", model="ministral-3:8b", logged_at="2026-10-03T10:00:00")


def test_a_decision_record_keeps_everything_a_reviewer_needs():
    failed = routed("t-1", "logistics", decided_by="checks")
    failed.failed_checks = [Failure("retrieval", "the help centre was not searched")]
    entry = record(failed)
    assert entry["ticket_id"] == "t-1" and entry["split"] == "test" and entry["outcome"] == "route"
    assert entry["failed_checks"] == [{"check": "retrieval", "reason": "the help centre was not searched"}]
    assert json.loads(json.dumps(entry)) == entry


def test_decisions_are_appended_and_the_latest_one_per_ticket_wins(tmp_path):
    log = tmp_path / "logs" / "decisions.jsonl"
    append_decisions(log, [record(routed("t-1", "logistics")), record(held("t-3"))])
    append_decisions(log, [record(closed("t-1", "reply", ["HC-05"]))])
    assert len(log.read_text(encoding="utf-8").splitlines()) == 3
    latest = read_decisions(log, "test")
    assert latest["t-1"]["outcome"] == "close"
    assert set(latest) == {"t-1", "t-3"}


def test_decisions_of_another_split_are_left_out(tmp_path):
    log = tmp_path / "decisions.jsonl"
    append_decisions(log, [record(held("t-3"), split="practice")])
    assert read_decisions(log, "test") == {}


def test_a_missing_log_reads_as_no_decisions(tmp_path):
    assert read_decisions(tmp_path / "nothing.jsonl", "test") == {}


def test_escalations_are_necessary_when_the_answer_key_also_wants_a_person():
    failed = routed("t-1", "logistics", decided_by="checks")
    failed.failed_checks = [Failure("retrieval", "the best help-centre match scores 1.20, below the threshold of 2.00")]
    decisions = {"t-1": record(failed), "t-2": record(routed("t-2", "billing")), "t-3": record(held("t-3"))}
    report = score_escalations(LABELS, decisions)
    assert (report.escalated, report.necessary, report.unnecessary) == (3, 2, 1)
    assert report.causes == [("a close held back: the help-centre match was below the threshold", ["t-1"])]


def test_the_most_common_unnecessary_escalations_come_first():
    labels = [label(f"t-{n}", "close", "billing", kind="invoice_copy") for n in range(1, 4)]
    decisions = {
        "t-1": record(routed("t-1", "billing")),
        "t-2": record(routed("t-2", "billing")),
        "t-3": record(held("t-3", decided_by="hard rules")),
    }
    report = score_escalations(labels, decisions)
    assert report.causes == [
        ("the model routed a routine question (invoice_copy)", ["t-1", "t-2"]),
        ("a hard rule fired on a routine question (legal)", ["t-3"]),
    ]
    text = escalation_report(report, "test")
    assert "unnecessary   3" in text
    assert "  2  the model routed a routine question (invoice_copy): t-1, t-2" in text
