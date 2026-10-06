import json
import shutil
from pathlib import Path

from perfect_model import PerfectModel
from test_agent import ScriptedModel, calls
from test_pipeline import ROUTE

from support_triage_agent.checks import Failure
from support_triage_agent.cli import card, main
from support_triage_agent.pipeline import TicketResult
from support_triage_agent.rules import Hit

REPO = Path(__file__).resolve().parents[1]
README = "# Sample\n\n<!-- results:start -->\nNot measured yet.\n<!-- results:end -->\n"
PRACTICE_TICKETS = 50


def workspace(tmp_path: Path) -> Path:
    shutil.copytree(REPO / "data", tmp_path / "data", ignore=shutil.ignore_patterns("*.py", "__pycache__"))
    shutil.copy(REPO / "acceptance.toml", tmp_path / "acceptance.toml")
    (tmp_path / "README.md").write_text(README, encoding="utf-8")
    return tmp_path


def record_practice(root: Path) -> PerfectModel:
    model = PerfectModel(root / "data", "practice")
    assert main(["accept", "--split", "practice", "--record"], root=root, transport=model) == 0
    return model


def test_record_then_replay_gives_the_same_report_without_a_model(tmp_path):
    root = workspace(tmp_path)
    model = record_practice(root)
    recorded = json.loads((root / "reports" / "practice" / "acceptance.json").read_text(encoding="utf-8"))
    run_dir = root / "runs" / "practice" / "ministral-3-8b"
    assert model.calls == len((run_dir / "calls.jsonl").read_text(encoding="utf-8").splitlines()) > 0
    run_info = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert run_info["items"] == PRACTICE_TICKETS and run_info["split"] == "practice"

    assert main(["accept", "--split", "practice"], root=root) == 0
    replayed = json.loads((root / "reports" / "practice" / "acceptance.json").read_text(encoding="utf-8"))
    assert replayed["criteria"] == recorded["criteria"]
    assert replayed["recorded_at"] == run_info["recorded_at"]
    assert replayed["outcome_split"] == recorded["outcome_split"]
    assert sum(replayed["outcome_split"].values()) == PRACTICE_TICKETS


def test_the_report_lists_the_split_and_the_reasons_behind_each_decision(tmp_path):
    root = workspace(tmp_path)
    record_practice(root)
    report = (root / "reports" / "practice" / "acceptance.md").read_text(encoding="utf-8")
    assert "Tickets wrongly closed (should have gone to a person)" in report
    assert "Close / route / hold:" in report
    assert "## Edge cases" in report


def test_every_decision_is_logged_and_escalations_can_be_scored(tmp_path, capsys):
    root = workspace(tmp_path)
    record_practice(root)
    main(["accept", "--split", "practice"], root=root)
    log = (root / "logs" / "decisions.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(log) == 2 * PRACTICE_TICKETS
    entry = json.loads(log[-1])
    assert entry["split"] == "practice" and entry["mode"] == "replay" and entry["outcome"] in ("close", "route", "hold")
    capsys.readouterr()
    assert main(["score-escalations", "--split", "practice"], root=root) == 0
    assert "Escalations on the practice split" in capsys.readouterr().out


def test_scoring_escalations_before_any_run_explains_what_to_do(tmp_path, capsys):
    root = workspace(tmp_path)
    assert main(["score-escalations"], root=root) == 2
    assert "make accept" in capsys.readouterr().err


def test_readme_block_follows_the_report_and_check_mode_detects_drift(tmp_path):
    root = workspace(tmp_path)
    record_practice(root)
    shutil.copy(root / "reports" / "practice" / "acceptance.json", root / "reports" / "acceptance.json")
    assert main(["readme", "--check"], root=root) == 1
    assert main(["readme"], root=root) == 0
    assert main(["readme", "--check"], root=root) == 0
    assert "Tickets wrongly closed" in (root / "README.md").read_text(encoding="utf-8")


def test_readme_without_a_report_explains_what_to_do(tmp_path, capsys):
    root = workspace(tmp_path)
    assert main(["readme", "--check"], root=root) == 2
    assert "make accept" in capsys.readouterr().err


def test_demo_replays_three_tickets(tmp_path, capsys):
    root = workspace(tmp_path)
    record_practice(root)
    capsys.readouterr()
    assert main(["demo", "--split", "practice"], root=root) == 0
    out = capsys.readouterr().out
    assert "closed with a reply" in out and "routed to" in out and "held for a person" in out


def test_replay_without_a_stored_run_explains_what_to_do(tmp_path, capsys):
    root = workspace(tmp_path)
    assert main(["accept"], root=root) == 2
    assert "make record" in capsys.readouterr().err


def test_run_triages_one_ticket_given_as_text(tmp_path, capsys):
    root = workspace(tmp_path)
    order = json.loads((root / "data" / "shop" / "orders.jsonl").read_text(encoding="utf-8").splitlines()[0])
    model = ScriptedModel(calls(("lookup_order", {"order_id": order["order_id"]})), "DONE", ROUTE)
    text = f"My parcel for {order['order_id']} is two weeks late and the tracking has not moved."
    assert main(["run", text], root=root, transport=model) == 0
    assert "routed to logistics" in capsys.readouterr().out
    assert model.requests[0]["options"]["num_ctx"] == 16384
    assert json.loads((root / "logs" / "decisions.jsonl").read_text(encoding="utf-8"))["split"] == "single ticket"


def test_run_reads_a_ticket_file(tmp_path, capsys):
    root = workspace(tmp_path)
    path = tmp_path / "complaint.txt"
    path.write_text("Subject: My sofa\n\nMy lawyer will contact you about my sofa.\n", encoding="utf-8")
    assert main(["run", str(path)], root=root, transport=ScriptedModel()) == 0
    out = capsys.readouterr().out
    assert out.startswith('complaint: "My sofa"')
    assert 'held for a person: Hard rule: legal threat ("lawyer")' in out


def test_cards_explain_each_outcome_in_plain_english():
    closed = TicketResult(
        "t", "close", "model", team="billing", reply="Hello,\nYour refund is on its way.", cited=["HC-11"]
    )
    stopped = TicketResult("t", "route", "checks", team="logistics", handover={**ROUTE["handover"]})
    stopped.failed_checks = [Failure("grounding", "the reply states 5 October 2026, which is not in the order record")]
    held = TicketResult(
        "t", "hold", "hard rules", hold_reason="Hard rule: safety risk.", hard_rules=[Hit("safety", "x")]
    )
    assert "closed with a reply, citing HC-11" in card("title", closed)
    assert "    Your refund is on its way." in card("title", closed)
    assert "the checks stopped the closing reply: the reply states 5 October 2026" in card("title", stopped)
    assert "next step: Open a carrier investigation." in card("title", stopped)
    assert card("title", held).endswith("held for a person: Hard rule: safety risk.")
