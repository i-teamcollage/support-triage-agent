"""Command line.

python -m support_triage_agent demo                three tickets from the stored run
python -m support_triage_agent accept              the acceptance test on the test split
python -m support_triage_agent accept --record     run it live on Ollama and store the run
python -m support_triage_agent run TICKET          triage one ticket live: a text file, or the text itself
python -m support_triage_agent readme              refresh the results table in README.md
python -m support_triage_agent score-escalations   necessary and unnecessary escalations in the decision log
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import textwrap
from datetime import UTC, date, datetime
from pathlib import Path

from .acceptance import (
    evaluate,
    load_criteria,
    report_dict,
    results_block,
    terminal_table,
    update_readme,
    write_reports,
)
from .escalations import append_decisions, decision_record, escalation_report, read_decisions, score_escalations
from .knowledge import KnowledgeBase
from .llm import DEFAULT_MODEL, LLM, ModelUnavailable, ReplayMiss, machine_description, ollama_info, run_dir_name
from .metrics import outcome_split, score
from .pipeline import TicketResult, triage
from .ticket import Ticket

ROOT = Path(__file__).resolve().parents[2]
TITLE = "Support triage agent: acceptance test"
NUM_CTX = 16384
HANDOVER_LABELS = {
    "summary": "summary",
    "customer_wants": "customer wants",
    "agent_found": "agent found",
    "order_facts": "order facts",
    "next_step": "next step",
}


class Workspace:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.data = self.root / "data"
        self.reports = self.root / "reports"
        self.readme = self.root / "README.md"
        self.acceptance = self.root / "acceptance.toml"
        self.log = self.root / "logs" / "decisions.jsonl"

    def runs_root(self, split: str) -> Path:
        return self.root / "runs" if split == "test" else self.root / "runs" / split

    def reports_dir(self, split: str) -> Path:
        return self.reports if split == "test" else self.reports / split

    def labels(self, split: str) -> list[dict]:
        lines = (self.data / split / "labels.jsonl").read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines if line.strip()]

    def ticket(self, split: str, label: dict) -> Ticket:
        return Ticket.parse(label["id"], (self.data / split / label["file"]).read_text(encoding="utf-8"))

    def knowledge(self) -> KnowledgeBase:
        return KnowledgeBase.from_dir(self.data / "shop")


def _mode(args: argparse.Namespace) -> str:
    if getattr(args, "record", False):
        return "record"
    if getattr(args, "live", False):
        return "live"
    return os.environ.get("AGENT_MODE", "replay")


def _run_split(ws: Workspace, split: str, llm: LLM) -> tuple[list[dict], dict[str, TicketResult]]:
    kb, labels, results = ws.knowledge(), ws.labels(split), {}
    for number, label in enumerate(labels, start=1):
        result = triage(ws.ticket(split, label), llm, kb)
        results[label["id"]] = result
        if llm.mode != "replay":
            outcome = f"{result.outcome} ({result.decided_by})"
            print(f"  [{number:>3}/{len(labels)}] {label['id']}  {outcome:<24} {result.seconds:6.1f} s", flush=True)
    return labels, results


def _log(ws: Workspace, results: list[TicketResult], *, split: str, mode: str, model: str) -> None:
    logged_at = datetime.now(UTC).isoformat(timespec="seconds")
    records = [decision_record(r, split=split, mode=mode, model=model, logged_at=logged_at) for r in results]
    append_decisions(ws.log, records)


def _run_info_path(ws: Workspace, split: str, model: str) -> Path:
    return ws.runs_root(split) / run_dir_name(model) / "run.json"


def _write_run_info(ws: Workspace, split: str, llm: LLM, results: dict[str, TicketResult], local_model: bool) -> None:
    seconds = [result.seconds for result in results.values() if result.seconds]
    info = {
        "recorded_at": date.today().isoformat(),
        "model": llm.model,
        **(ollama_info(llm.model) if local_model else {}),
        "machine": machine_description(),
        "split": split,
        "items": len(results),
        "median_seconds_per_item": round(statistics.median(seconds), 2) if seconds else None,
        "item_seconds": {ticket_id: result.seconds for ticket_id, result in results.items()},
    }
    path = _run_info_path(ws, split, llm.model)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")


def cmd_accept(args: argparse.Namespace, ws: Workspace, transport=None) -> int:
    mode = _mode(args)
    llm = LLM(model=args.model, mode=mode, runs_root=ws.runs_root(args.split), num_ctx=NUM_CTX, transport=transport)
    if mode == "record":
        llm.start_recording()
    print(f"Acceptance test, {args.split} split, model {args.model}, mode {mode}")
    try:
        labels, results = _run_split(ws, args.split, llm)
    except (ReplayMiss, ModelUnavailable) as error:
        print(f"\n{error}", file=sys.stderr)
        return 2
    _log(ws, list(results.values()), split=args.split, mode=mode, model=args.model)
    if mode == "record":
        _write_run_info(ws, args.split, llm, results, local_model=transport is None)
    info_path = _run_info_path(ws, args.split, args.model)
    info = json.loads(info_path.read_text(encoding="utf-8")) if mode != "live" and info_path.exists() else {}

    measures, details = score(labels, results)
    outcomes = evaluate(load_criteria(ws.acceptance), measures)
    seconds = [result.seconds for result in results.values() if result.seconds]
    split_counts = outcome_split(results)
    meta = {
        "title": TITLE,
        "split": args.split,
        "items": len(labels),
        "model": args.model,
        "machine": info.get("machine") or machine_description(),
        "recorded_at": info.get("recorded_at"),
        "ollama_version": info.get("ollama_version"),
        "model_digest": info.get("model_digest"),
        "median_seconds_per_item": round(statistics.median(seconds), 1) if seconds else None,
        "outcome_split": split_counts,
    }
    report = report_dict(outcomes, meta)
    out_dir = ws.reports_dir(args.split)
    write_reports(report, out_dir, details)
    print()
    print(terminal_table(outcomes))
    print(f"\n  close {split_counts['close']}, route {split_counts['route']}, hold {split_counts['hold']}")
    print(f"\n{'PASSED' if report['passed'] else 'FAILED'}: details in {out_dir}/acceptance.md")
    return 0 if report["passed"] else 1


def _indented(text: str, prefix: str = "    ") -> list[str]:
    lines = []
    for paragraph in text.strip().splitlines():
        wrapped = textwrap.wrap(paragraph, width=100 - len(prefix)) or [""]
        lines += [f"{prefix}{line}".rstrip() for line in wrapped]
    return lines


def _looked_at(result: TicketResult) -> str:
    seen = []
    for call in result.tool_calls:
        arguments = call["arguments"] if isinstance(call["arguments"], dict) else {"": call["arguments"]}
        value = next(iter(arguments.values()), "")
        seen.append(f"{call['name']}({json.dumps(value, ensure_ascii=False)})")
    return ", ".join(seen)


def card(title: str, result: TicketResult) -> str:
    lines = [title]
    if result.tool_calls:
        lines.append(f"  looked up: {_looked_at(result)}")
    if result.outcome == "close":
        lines.append(f"  -> closed with a reply, citing {', '.join(result.cited)}")
        lines += _indented(result.reply or "")
    elif result.outcome == "route":
        if result.decided_by == "checks":
            why = f"the checks stopped the closing reply: {result.failed_checks[0].reason}"
        else:
            why = "a person has to act, with this handover"
        lines.append(f"  -> routed to {result.team}: {why}")
        for key, label in HANDOVER_LABELS.items():
            value = (result.handover or {}).get(key, "").split("\n\nDraft reply:")[0].strip()
            if value:
                lines += _indented(f"{label}: {value}")
    else:
        lines.append(f"  -> held for a person: {result.hold_reason}")
    return "\n".join(lines)


def _title(label: dict, ticket: Ticket) -> str:
    kind = {"routine": "routine ticket", "complex": "complex ticket", "edge": "edge case"}[label["category"]]
    return f'{label["id"]}  {kind}: "{ticket.subject}"'


def cmd_demo(args: argparse.Namespace, ws: Workspace, transport=None) -> int:
    runs_root = ws.runs_root(args.split)
    llm = LLM(model=args.model, mode=_mode(args), runs_root=runs_root, num_ctx=NUM_CTX, transport=transport)
    try:
        labels, results = _run_split(ws, args.split, llm)
    except (ReplayMiss, ModelUnavailable) as error:
        print(error, file=sys.stderr)
        return 2
    picks = [
        next((label for label in labels if results[label["id"]].outcome == "close"), None),
        next((label for label in labels if results[label["id"]].decided_by == "checks"), None)
        or next((label for label in labels if results[label["id"]].outcome == "route"), None),
        next((label for label in labels if results[label["id"]].decided_by == "hard rules"), None),
    ]
    for label in filter(None, picks):
        print(card(_title(label, ws.ticket(args.split, label)), results[label["id"]]))
        print()
    return 0


def _read_ticket(argument: str) -> tuple[str, str]:
    """The ticket id and text: from a file when the argument names one, otherwise the argument itself."""
    if "\n" not in argument and len(argument) < 250:
        try:
            path = Path(argument)
            if path.is_file():
                return path.stem, path.read_text(encoding="utf-8")
        except OSError:
            pass
    return "ticket", argument


def cmd_run(args: argparse.Namespace, ws: Workspace, transport=None) -> int:
    mode = "replay" if args.replay else "live"
    llm = LLM(model=args.model, mode=mode, runs_root=ws.runs_root("test"), num_ctx=NUM_CTX, transport=transport)
    ticket_id, text = _read_ticket(args.ticket)
    ticket = Ticket.parse(ticket_id, text, today=date.today())
    try:
        result = triage(ticket, llm, ws.knowledge())
    except (ReplayMiss, ModelUnavailable) as error:
        print(error, file=sys.stderr)
        return 2
    _log(ws, [result], split="single ticket", mode=mode, model=args.model)
    print(card(f'{ticket.id}: "{ticket.subject}"', result))
    return 0


def cmd_readme(args: argparse.Namespace, ws: Workspace, transport=None) -> int:
    report_path = ws.reports / "acceptance.json"
    if not report_path.exists():
        print(f"No acceptance report at {report_path} yet: run `make accept` first.", file=sys.stderr)
        return 2
    report = json.loads(report_path.read_text(encoding="utf-8"))
    changed = update_readme(ws.readme, results_block(report), check=args.check)
    if args.check:
        print("README results are out of date: run `make readme`" if changed else "README results are up to date")
        return 1 if changed else 0
    print("README results updated" if changed else "README results already up to date")
    return 0


def cmd_score_escalations(args: argparse.Namespace, ws: Workspace, transport=None) -> int:
    decisions = read_decisions(ws.log, args.split)
    if not decisions:
        print(f"No decisions for the {args.split} split in {ws.log} yet: run `make accept` first.", file=sys.stderr)
        return 2
    labels = ws.labels(args.split)
    print(escalation_report(score_escalations(labels, decisions), args.split, len(labels)))
    return 0


def main(argv: list[str] | None = None, *, root: Path = ROOT, transport=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m support_triage_agent", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    model = os.environ.get("AGENT_MODEL", DEFAULT_MODEL)
    for name in ("demo", "accept"):
        command = commands.add_parser(name)
        command.add_argument("--live", action="store_true", help="ask the model instead of the stored run")
        command.add_argument("--record", action="store_true", help="ask the model and store the run")
        command.add_argument("--model", default=model)
        command.add_argument("--split", default="test", choices=["test", "practice"])
    run = commands.add_parser("run")
    run.add_argument("ticket", help="a text file with the ticket, or the ticket text itself")
    run.add_argument("--replay", action="store_true")
    run.add_argument("--model", default=model)
    readme = commands.add_parser("readme")
    readme.add_argument("--check", action="store_true")
    escalations = commands.add_parser("score-escalations")
    escalations.add_argument("--split", default="test", choices=["test", "practice"])
    args = parser.parse_args(argv)
    handler = {
        "demo": cmd_demo,
        "accept": cmd_accept,
        "run": cmd_run,
        "readme": cmd_readme,
        "score-escalations": cmd_score_escalations,
    }[args.command]
    return handler(args, Workspace(root), transport)
