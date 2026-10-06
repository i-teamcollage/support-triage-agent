"""Dates, amounts, durations and codes in plain English text.

Replies are checked against the order record and the help centre, and scored against the answer key.
Both sides go through this module, so "7 October", "07/10/2026" and "2026-10-07" are the same date,
and "€39", "39,00 €" and "EUR 39.00" are the same amount.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Any

CENT = Decimal("0.01")

MONTHS = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sept": 9,
    "sep": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}
_MONTH = "|".join(sorted(MONTHS, key=len, reverse=True))
_ORDINAL = r"(?:st|nd|rd|th)?"

_DATE_PATTERNS = [
    ("ymd", re.compile(r"(?<![\d-])(\d{4})-(\d{2})-(\d{2})(?![\d-])")),
    ("dmy", re.compile(r"(?<![\d./])(\d{1,2})[./](\d{1,2})[./](\d{4})(?![\d./])")),
    (
        "d_month",
        re.compile(rf"(?<!\w)(\d{{1,2}}){_ORDINAL}(?:\s+of)?\s+({_MONTH})\.?(?:,?\s+(\d{{4}}))?(?!\w)", re.I),
    ),
    ("month_d", re.compile(rf"(?<!\w)({_MONTH})\.?\s+(\d{{1,2}}){_ORDINAL}(?:,?\s+(\d{{4}}))?(?!\w)", re.I)),
]


def _to_date(kind: str, groups: tuple[str | None, ...], year: int | None) -> date | None:
    try:
        if kind == "ymd":
            return date(int(groups[0]), int(groups[1]), int(groups[2]))
        if kind == "dmy":
            return date(int(groups[2]), int(groups[1]), int(groups[0]))
        if kind == "d_month":
            day, month, written_year = groups
        else:
            month, day, written_year = groups
        if month == "may":  # the verb, not the month
            return None
        chosen = int(written_year) if written_year else year
        if chosen is None:
            return None
        return date(chosen, MONTHS[month.lower()], int(day))
    except (ValueError, KeyError, TypeError):
        return None


def find_dates(text: str, year: int | None = None) -> list[tuple[str, date]]:
    """Every date in the text as (exact quote, date), in reading order.

    A date written without a year ("7 October") takes `year`, the year of the ticket; without it, it is skipped.
    Numeric dates are read day first, as in Europe.
    """
    spans = []
    for kind, pattern in _DATE_PATTERNS:
        for match in pattern.finditer(text):
            value = _to_date(kind, match.groups(), year)
            if value is not None:
                spans.append((match.start(), match.end(), match.group(0), value))
    spans.sort(key=lambda span: (span[0], -span[1]))
    found, last_end = [], -1
    for start, end, quote, value in spans:
        if start >= last_end:
            found.append((quote, value))
            last_end = end
    return found


_NUMBER = r"\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?"
_AMOUNT = re.compile(
    rf"(?:€|\bEUR)\s?(?P<n1>{_NUMBER})(?!\d)|(?<![\d.,])(?P<n2>{_NUMBER})\s?(?:€|EUR\b|euros?\b)", re.IGNORECASE
)


def _to_decimal(number: str) -> Decimal:
    decimals = re.fullmatch(r"(.*?)[.,](\d{1,2})", number)
    if decimals and not re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", number):
        whole = re.sub(r"\D", "", decimals.group(1)) or "0"
        return Decimal(f"{whole}.{decimals.group(2)}").quantize(CENT)
    return Decimal(re.sub(r"\D", "", number)).quantize(CENT)


def find_amounts(text: str) -> list[tuple[str, Decimal]]:
    """Every amount in euros as (exact quote, value with two decimals), in reading order."""
    return [(match.group(0), _to_decimal(match.group("n1") or match.group("n2"))) for match in _AMOUNT.finditer(text)]


def dates_in(text: str, year: int | None = None) -> set[date]:
    return {value for _, value in find_dates(text, year)}


def amounts_in(text: str) -> set[Decimal]:
    return {value for _, value in find_amounts(text)}


_NUMBER_WORDS = {
    1: "one",
    2: "two",
    3: "three",
    4: "four",
    5: "five",
    6: "six",
    7: "seven",
    8: "eight",
    9: "nine",
    10: "ten",
    11: "eleven",
    12: "twelve",
    14: "fourteen",
    15: "fifteen",
    20: "twenty",
    24: "twenty-four",
    30: "thirty",
    45: "forty-five",
    48: "forty-eight",
    60: "sixty",
    90: "ninety",
}


def _duration_pattern(value: int, unit: str) -> re.Pattern:
    number = rf"(?<![\d.,]){value}"
    if value in _NUMBER_WORDS:
        number = rf"(?:{number}|(?<![\w-]){_NUMBER_WORDS[value]})"
    singular = unit.rstrip("s")
    return re.compile(rf"{number}(?:\s+|-)(?:(?:working|business|calendar)\s+)?{singular}s?\b", re.IGNORECASE)


def _compact(text: str) -> str:
    return re.sub(r"[^0-9a-z]", "", text.lower())


def fact_stated(fact: dict[str, Any], text: str, year: int | None = None) -> bool:
    """True when the text states the fact: a date, an amount, a duration such as 30 days, or a code."""
    kind = fact["type"]
    if kind == "date":
        return date.fromisoformat(fact["value"]) in dates_in(text, year)
    if kind == "amount":
        return Decimal(fact["value"]).quantize(CENT) in amounts_in(text)
    if kind == "duration":
        return bool(_duration_pattern(int(fact["value"]), fact["unit"]).search(text))
    if kind == "code":
        return _compact(fact["value"]) in _compact(text)
    raise ValueError(f"unknown fact type {kind!r}")


def describe_fact(fact: dict[str, Any]) -> str:
    kind = fact["type"]
    if kind == "date":
        return f"the date {fact['value']}"
    if kind == "amount":
        return f"the amount €{Decimal(fact['value']).quantize(CENT)}"
    if kind == "duration":
        return f"{fact['value']} {fact['unit']}"
    return str(fact["value"])
