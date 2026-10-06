"""One inbound ticket: its text, and the few header lines a help desk adds (sender, date, subject)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from .knowledge import find_order_ids

_HEADER = re.compile(r"(From|Received|Subject):\s*(.*)")


@dataclass(frozen=True)
class Ticket:
    id: str
    text: str
    received: date
    subject: str
    sender: str

    @classmethod
    def parse(cls, ticket_id: str, text: str, today: date | None = None) -> Ticket:
        headers: dict[str, str] = {}
        for line in text.splitlines():
            match = _HEADER.match(line)
            if not match:
                break
            headers[match.group(1).lower()] = match.group(2).strip()
        try:
            received = date.fromisoformat(headers.get("received", "")[:10])
        except ValueError:
            received = today or date.today()
        first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
        subject = headers.get("subject") or first_line[:80]
        return cls(ticket_id, text, received, subject, headers.get("from", ""))

    @property
    def order_ids(self) -> list[str]:
        """The order numbers the ticket names."""
        return find_order_ids(self.text)
