"""Generate the made-up shop: its help centre, past tickets, orders, and the inbound tickets with their labels.

    python data/generate.py           write everything under data/
    python data/generate.py --check   regenerate in memory and compare with the committed files

Fixed seeds, the repo's own word lists, no Faker: the output never changes unless this file does.
Hollinvale Home, its carriers, customers, companies and orders are fictional.

Every order a ticket refers to is built for that ticket, and its record shows the order as it stood on the
day the ticket arrived. The other orders are filler, as they stood on the last day of the ticket window.

Labels, one per ticket: the expected outcome (close, route or hold), the owning team (`hold` for edge
cases), the relevant help-centre articles, and the key facts a correct closing reply must state (empty
when the ticket should not be closed).
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from helpcentre import ARTICLES  # noqa: E402
from templates import (  # noqa: E402
    CHATTY,
    DAMAGES,
    ERRORS,
    GREETINGS,
    PARTS,
    PAST,
    REASONS,
    SIGNOFFS,
    TICKETS,
    TYPOS,
)
from words import (  # noqa: E402
    ASSEMBLY_COUNTRIES,
    CARRIERS,
    CITIES,
    COMPANIES,
    COUNTRIES,
    COUNTRY_WEIGHTS,
    EXPRESS_COUNTRIES,
    FIRST_NAMES,
    LAST_NAMES,
    NO_LARGE_ITEMS,
    PAY_LATER_COUNTRIES,
    PRODUCTS,
    STANDARD_DAYS,
    TIMES_OF_DAY,
    TRACKING_PREFIX,
    WRONG_ITEM_SWAPS,
)

SHOP_SEED = 7
SPLITS = {"practice": (1, 50, "p"), "test": (2, 100, "t")}
MIX = (("routine", 0.6), ("complex", 0.3), ("edge", 0.1))
N_ORDERS, N_PAST = 300, 200
FIRST_DAY, LAST_DAY = date(2026, 9, 21), date(2026, 10, 2)  # inbound tickets arrive in these two weeks
FIRST_ORDER_DAY = date(2026, 6, 1)
PAST_FIRST, PAST_LAST = date(2026, 3, 2), date(2026, 9, 18)

# kind: owning team and the help-centre articles a reply can rest on
ROUTINE = {
    "delivery_eta": ("logistics", ["HC-05", "HC-02", "HC-04"]),
    "multi_parcel": ("logistics", ["HC-14", "HC-05", "HC-02"]),
    "return_window": ("logistics", ["HC-10"]),
    "return_policy": ("logistics", ["HC-10"]),
    "refund_status": ("billing", ["HC-11"]),
    "delivery_cost": ("logistics", ["HC-04"]),
    "cancel_shipped": ("logistics", ["HC-01", "HC-10"]),
    "invoice_copy": ("billing", ["HC-18"]),
    "account_locked": ("tech", ["HC-24"]),
    "pay_later_due": ("billing", ["HC-17"]),
    "pay_later_limit": ("billing", ["HC-17"]),
    "discount_minimum": ("billing", ["HC-19"]),
    "assembly_service": ("logistics", ["HC-22"]),
    "warranty_period": ("logistics", ["HC-21"]),
}
COMPLEX = {
    "double_charge": ("billing", ["HC-16"]),
    "refund_overdue": ("billing", ["HC-11"]),
    "price_drop": ("billing", ["HC-20"]),
    "invoice_correction": ("billing", ["HC-18"]),
    "reminder_fee_dispute": ("billing", ["HC-17"]),
    "lost_parcel": ("logistics", ["HC-08"]),
    "damaged_item": ("logistics", ["HC-13"]),
    "wrong_item": ("logistics", ["HC-15"]),
    "missing_parts_claim": ("logistics", ["HC-14"]),
    "missed_two_person": ("logistics", ["HC-06"]),
    "return_pickup_missed": ("logistics", ["HC-10"]),
    "checkout_error": ("tech", ["HC-16"]),
    "reset_link_invalid": ("tech", ["HC-24"]),
    "app_crash": ("tech", []),
    "email_change_error": ("tech", ["HC-24"]),
    "discount_code_error": ("tech", ["HC-19"]),
}
EDGE = {
    "legal_threat": ["HC-08"],
    "data_deletion": ["HC-25"],
    "fraud": [],
    "safety": ["HC-13"],
    "injection": [],
}
OUTCOME = {"routine": "close", "complex": "route", "edge": "hold"}
STATUSES = (
    "received",
    "packed",
    "shipped",
    "delayed",
    "partly delivered",
    "delivered",
    "return in progress",
    "returned",
    "cancelled",
)

TWO_PERSON_FEE, EXPRESS_FEE, STANDARD_FEE = Decimal("39.00"), Decimal("9.95"), Decimal("4.95")
FREE_DELIVERY_OVER, COLLECTION_FEE, REMINDER_FEE = Decimal("75"), Decimal("29.00"), Decimal("5.00")
PAY_LATER_RANGE = (Decimal("20"), Decimal("1500"))
SLOTS = ["08:00-12:00", "12:00-16:00", "16:00-20:00"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]
TRANSIT_EVENTS = {
    "Veloway Parcel": ["picked up by Veloway Parcel", "arrived at the sorting centre", "in transit to the local depot"],
    "Tramline Couriers": ["picked up by Tramline Couriers", "at the Tramline hub"],
    "Brookhaul": ["picked up by Brookhaul", "arrived at the Brookhaul hub", "arrived at the local Brookhaul depot"],
}
VAT_FORMATS = {"NL": "NL#########B01", "FR": "FR## #########", "AT": "ATU########", "BE": "BE0#########"}
VAT_FORMATS.update({"DE": "DE#########", "IE": "IE#######W"})

CATALOGUE = [
    {"sku": sku, "name": name, "short": short, "price": Decimal(price), "flags": frozenset(flags.split())}
    for sku, name, short, price, flags in PRODUCTS
]
LARGE_SKUS = frozenset(product["sku"] for product in CATALOGUE if "large" in product["flags"])


# ---------------------------------------------------------------- calendar


def iso(day: date | None) -> str | None:
    return day.isoformat() if day else None


def add_working_days(day: date, n: int) -> date:
    """n working days after day (before it when n is negative). Weekends do not count."""
    step = 1 if n > 0 else -1
    for _ in range(abs(n)):
        day += timedelta(days=step)
        while day.weekday() >= 5:
            day += timedelta(days=step)
    return day


def working_day_on_or_after(day: date) -> date:
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


def working_day_on_or_before(day: date) -> date:
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def working_days_between(start: date, end: date) -> int:
    """Working days after start, up to and including end."""
    count, day = 0, start
    while day < end:
        day += timedelta(days=1)
        count += day.weekday() < 5
    return count


def when(rng: random.Random, day: date, today: date) -> str:
    """How a customer refers to a past day: "today", "yesterday", "on Tuesday", "last Friday", "on 14 September"."""
    gap = (today - day).days
    if gap == 0:
        return "today"
    if gap == 1:
        return "yesterday"
    if gap < 7:
        return f"on {WEEKDAYS[day.weekday()]}" if day.weekday() < today.weekday() else f"last {WEEKDAYS[day.weekday()]}"
    return rng.choice([f"on {day.day} {MONTHS[day.month - 1]}", f"on {day.day} {MONTHS[day.month - 1]}", "last week"])


def day_name(day: date, today: date) -> str:
    """A past day as a bare name: "Tuesday" in the same week, otherwise "29 September"."""
    if 0 < (today - day).days < 7 and day.weekday() < today.weekday():
        return WEEKDAYS[day.weekday()]
    return f"{day.day} {MONTHS[day.month - 1]}"


# ---------------------------------------------------------------- shop pieces


def money(value: Decimal) -> str:
    return f"€{value:,.2f}"


def said(rng: random.Random, value: Decimal) -> str:
    """An amount the way a customer writes it."""
    whole = value == value.to_integral_value()
    forms = [money(value), f"€{value:,.0f}" if whole else money(value), f"{value:.2f} euros", f"EUR {value:.2f}"]
    return rng.choice(forms)


def products(need=(), avoid=()) -> list[dict]:
    return [p for p in CATALOGUE if set(need) <= p["flags"] and not set(avoid) & p["flags"]]


def countable(items: list[dict]) -> list[dict]:
    """Products whose everyday name takes "a": a lamp, not a pillows."""
    return [p for p in items if not p["short"].endswith("s")]


def display(product: dict) -> str:
    return product["name"].split(",")[0]


def items_total(lines) -> Decimal:
    return sum((product["price"] * qty for product, qty in lines), Decimal("0.00"))


def delivery_cost(method: str, lines) -> Decimal:
    if method == "two-person":
        return TWO_PERSON_FEE
    if method == "express":
        return EXPRESS_FEE
    return Decimal("0.00") if items_total(lines) > FREE_DELIVERY_OVER else STANDARD_FEE


def order_total(method: str, lines) -> Decimal:
    return items_total(lines) + delivery_cost(method, lines)


@dataclass
class Ctx:
    """What a scenario needs: randomness, the day the ticket arrived, and the tracking numbers already used."""

    rng: random.Random
    today: date
    taken: set[str]


def make_customer(rng: random.Random, allowed=None, avoid=()) -> dict:
    pool = [cc for cc in COUNTRY_WEIGHTS if (allowed is None or cc in allowed) and cc not in avoid]
    cc = rng.choices(pool, weights=[COUNTRY_WEIGHTS[c] for c in pool])[0]
    first, last = rng.choice(FIRST_NAMES[cc]), rng.choice(LAST_NAMES[cc])
    return {
        "first": first,
        "name": f"{first} {last}",
        "city": rng.choice(CITIES[cc]),
        "cc": cc,
        "country": COUNTRIES[cc],
    }


def add_small_items(rng: random.Random, lines: list, most: int = 2) -> list:
    for _ in range(rng.randint(0, most)):
        product = rng.choice(products(avoid=("large",)))
        if all(product is not chosen for chosen, _ in lines):
            lines.append((product, 2 if product["price"] < 40 and rng.random() < 0.25 else 1))
    return lines


def method_for(rng: random.Random, lines, cc: str, prefer: str | None = None) -> str:
    if any("large" in product["flags"] for product, _ in lines):
        return "two-person"
    if prefer:
        return prefer
    return "express" if cc in EXPRESS_COUNTRIES and rng.random() < 0.15 else "standard"


def parcel_groups(lines, method: str) -> list[tuple[str, list[dict]]]:
    large = [product for product, _ in lines if "large" in product["flags"]]
    small = [product for product, _ in lines if "large" not in product["flags"]]
    if method == "two-person":
        return [(CARRIERS["two-person"], large)] + ([(CARRIERS["standard"], small)] if small else [])
    return [(CARRIERS[method], large + small)]


def transit(rng: random.Random, carrier: str, cc: str) -> int:
    if carrier == CARRIERS["express"]:
        return 1
    if carrier == CARRIERS["two-person"]:
        return rng.randint(5, 10)
    return rng.randint(*STANDARD_DAYS[cc])


def tracking(ctx: Ctx, carrier: str) -> str:
    prefix, digits = TRACKING_PREFIX[carrier]
    while True:
        number = prefix + "".join(str(ctx.rng.randrange(10)) for _ in range(digits))
        if number not in ctx.taken:
            ctx.taken.add(number)
            return number


def parcel(ctx, carrier, items, shipped, expected, delivered=None, first_expected=None, slot=None, update=None):
    if update is None:
        update = (delivered, "delivered") if delivered else (shipped, TRANSIT_EVENTS[carrier][0])
    return {
        "carrier": carrier,
        "tracking": tracking(ctx, carrier),
        "items": [product["name"] for product in items],
        "shipped_on": iso(shipped),
        "expected_on": iso(expected),
        "first_expected_on": iso(first_expected),
        "delivered_on": iso(delivered),
        "slot": slot,
        "last_update": {"date": iso(update[0]), "event": update[1]},
    }


def arrived(ctx: Ctx, carrier: str, items, shipped: date, delivered: date) -> dict:
    return parcel(ctx, carrier, items, shipped, delivered, delivered)


def moving(ctx: Ctx, carrier, items, shipped, expected, *, first_expected=None, slot=None, stalled=False) -> dict:
    """A parcel still on its way on the day of the ticket. A stalled one has not been scanned for days."""
    events = TRANSIT_EVENTS[carrier]
    step = 1 if stalled else min(len(events) - 1, working_days_between(shipped, ctx.today))
    update_day = min(add_working_days(shipped, step), ctx.today)
    return parcel(ctx, carrier, items, shipped, expected, None, first_expected, slot, (update_day, events[step]))


def forward_parcels(ctx: Ctx, cc: str, lines, method: str, shipped: date) -> list[dict]:
    """Parcels that left on `shipped`, as they stand today: delivered once their expected day has passed."""
    parcels = []
    for carrier, items in parcel_groups(lines, method):
        expected = add_working_days(shipped, transit(ctx.rng, carrier, cc))
        if expected < ctx.today:
            parcels.append(arrived(ctx, carrier, items, shipped, expected))
        else:
            parcels.append(moving(ctx, carrier, items, shipped, expected))
    return parcels


def status_of(parcels: list[dict]) -> str:
    delivered = sum(bool(p["delivered_on"]) for p in parcels)
    if not delivered:
        return "delayed" if any(p["first_expected_on"] for p in parcels) else "shipped"
    return "delivered" if delivered == len(parcels) else "partly delivered"


def pay_method(rng: random.Random, customer: dict, total: Decimal, later: bool = True) -> str:
    options = [("card", 65), ("bank transfer", 15)]
    low, high = PAY_LATER_RANGE
    if later and customer["cc"] in PAY_LATER_COUNTRIES and low <= total <= high:
        options.append(("Pay in 30 days", 20))
    return rng.choices([name for name, _ in options], weights=[weight for _, weight in options])[0]


def placed_and_paid(rng: random.Random, method: str, shipped: date) -> tuple[date, date | None]:
    """When an order that shipped on `shipped` was placed and paid. Bank transfers ship once the money is in."""
    if method == "bank transfer":
        paid = add_working_days(shipped, -rng.choice([0, 1]))
        return add_working_days(paid, -rng.choice([1, 2])), paid
    placed = shipped - timedelta(days=rng.choice([0, 0, 1, 1, 2]))
    return placed, placed if method == "card" else None


def payment(rng: random.Random, method: str, paid: date | None, shipped: date | None, today: date) -> dict:
    record = {"method": method, "status": "paid", "paid_on": iso(paid), "due_on": None, "refunded_on": None}
    record["reminders"] = []
    if method == "Pay in 30 days":
        due = shipped + timedelta(days=30) if shipped else None
        record.update(status="open", paid_on=None, due_on=iso(due))
        if due and due < today:  # paid in time, a few days before the due date
            record.update(status="paid", paid_on=iso(max(shipped, due - timedelta(days=rng.randint(0, 9)))))
    return record


def assemble(customer, lines, method, placed, pay, parcels, status, returned=None) -> dict:
    delivered = [p["delivered_on"] for p in parcels if p["delivered_on"]]
    every_parcel_delivered = bool(parcels) and len(delivered) == len(parcels)
    return_by = date.fromisoformat(max(delivered)) + timedelta(days=30) if every_parcel_delivered else None
    return {
        "order_id": None,
        "placed_on": iso(placed),
        "customer": {"name": customer["name"], "city": customer["city"], "country": customer["country"]},
        "status": status,
        "items": [
            {"sku": p["sku"], "name": p["name"], "qty": qty, "unit_price": f"{p['price']:.2f}"} for p, qty in lines
        ],
        "delivery": {"method": method, "cost": f"{delivery_cost(method, lines):.2f}"},
        "total": f"{order_total(method, lines):.2f}",
        "payment": pay,
        "invoice": {"emailed_on": min(p["shipped_on"] for p in parcels)} if parcels else None,
        "parcels": parcels,
        "return_by": iso(return_by),
        "return": returned,
    }


def shipped_order(ctx: Ctx, customer: dict, lines, method: str, shipped: date, *, later=True) -> dict:
    """An order that left the warehouse on `shipped`, shown as it stands on the day of the ticket."""
    rng = ctx.rng
    paying = pay_method(rng, customer, order_total(method, lines), later)
    placed, paid = placed_and_paid(rng, paying, shipped)
    parcels = forward_parcels(ctx, customer["cc"], lines, method, shipped)
    return assemble(
        customer, lines, method, placed, payment(rng, paying, paid, shipped, ctx.today), parcels, status_of(parcels)
    )


def one_parcel_order(ctx, customer, lines, method, shipped, delivered=None, *, later=True, **moving_options) -> dict:
    """An order travelling in one parcel, delivered on `delivered` or still on its way."""
    rng = ctx.rng
    paying = pay_method(rng, customer, order_total(method, lines), later)
    placed, paid = placed_and_paid(rng, paying, shipped)
    [(carrier, items)] = parcel_groups(lines, method)
    if delivered:
        parcels = [arrived(ctx, carrier, items, shipped, delivered)]
    else:
        expected = moving_options.pop("expected")
        parcels = [moving(ctx, carrier, items, shipped, expected, **moving_options)]
    return assemble(
        customer, lines, method, placed, payment(rng, paying, paid, shipped, ctx.today), parcels, status_of(parcels)
    )


def refund_for(order: dict, returned_names: list[str], collected: bool) -> Decimal:
    prices = {item["name"]: Decimal(item["unit_price"]) * item["qty"] for item in order["items"]}
    amount = sum((prices[name] for name in returned_names), Decimal("0.00"))
    if collected:
        amount -= COLLECTION_FEE
    if set(returned_names) == set(prices) and order["delivery"]["method"] != "two-person":
        amount += Decimal(order["delivery"]["cost"])
    return amount


def add_return(
    order: dict, names: list[str], requested: date, *, collection=None, collected=None, received=None, issued=None
) -> dict:
    """Record a return on a delivered order, with its refund once the items are back at the warehouse."""
    refund = None
    if received:
        amount = refund_for(order, names, collection is not None)
        refund = {
            "amount": f"{amount:.2f}",
            "status": "issued" if issued else "processing",
            "expected_by": iso(add_working_days(received, 5)),
            "issued_on": iso(issued),
        }
    order["return"] = {
        "items": names,
        "requested_on": iso(requested),
        "collection_on": iso(collection),
        "collected_on": iso(collected),
        "received_on": iso(received),
        "refund": refund,
    }
    whole = set(names) == {item["name"] for item in order["items"]}
    order["status"] = "returned" if issued and whole else "delivered" if issued else "return in progress"
    return order


# ---------------------------------------------------------------- scenarios, one per kind of ticket


@dataclass
class Scenario:
    customer: dict
    slots: dict = field(default_factory=dict)
    facts: list = field(default_factory=list)
    order: dict | None = None
    articles: list | None = None  # when the scenario adds to the kind's usual articles
    bodies: str = "bodies"
    extras: list | None = None  # when only some of the kind's extra sentences fit this order


def date_fact(day) -> dict:
    return {"type": "date", "value": day if isinstance(day, str) else day.isoformat()}


def amount_fact(value: str) -> dict:
    return {"type": "amount", "value": value}


def duration_fact(value: int, unit: str) -> dict:
    return {"type": "duration", "value": value, "unit": unit}


def sc_delivery_eta(ctx: Ctx) -> Scenario:
    rng, today = ctx.rng, ctx.today
    variant = rng.choices(["standard", "express", "two-person"], weights=[6, 2, 2])[0]
    if variant == "express":
        customer = make_customer(rng, allowed=EXPRESS_COUNTRIES)
    else:
        customer = make_customer(rng, avoid=NO_LARGE_ITEMS if variant == "two-person" else ())
    if variant == "two-person":
        main = rng.choice(products(need=("large",)))
        lines = [(main, 1)]
    else:
        main = rng.choice(countable(products(avoid=("large",))))
        lines = add_small_items(rng, [(main, 1)])
    method = method_for(rng, lines, customer["cc"], prefer=variant if variant != "two-person" else None)
    carrier = CARRIERS[method]
    days = transit(rng, carrier, customer["cc"])
    expected = add_working_days(working_day_on_or_after(today), rng.randint(0, min(3, days - 1)))
    shipped = add_working_days(expected, -days)
    options = {"expected": expected}
    if method == "two-person" and rng.random() < 0.5:
        options["slot"] = rng.choice(SLOTS)
    elif method == "standard" and rng.random() < 0.25:
        first = add_working_days(expected, -rng.randint(1, 2))
        if first > shipped:
            options["first_expected"] = first
    order = one_parcel_order(ctx, customer, lines, method, shipped, **options)
    slots = {"item": main["short"], "placed": when(rng, date.fromisoformat(order["placed_on"]), today)}
    articles = ["HC-06"] if method == "two-person" else None
    return Scenario(customer, slots, [date_fact(expected)], order, articles)


def sc_multi_parcel(ctx: Ctx) -> Scenario:
    rng, today = ctx.rng, ctx.today
    customer = make_customer(rng, avoid=NO_LARGE_ITEMS)
    delivered = working_day_on_or_before(today - timedelta(days=rng.randint(1, 4)))
    expected = add_working_days(working_day_on_or_after(today), rng.randint(0, 2))
    small = countable(products(avoid=("large",)))
    if rng.random() < 0.5:
        large = rng.choice(products(need=("large",)))
        first_items, later_items = [rng.choice(small)], [large]
        lines = [(first_items[0], 1), (large, 1)]
        method, carriers = "two-person", (CARRIERS["standard"], CARRIERS["two-person"])
        later_days = rng.randint(5, 10)
    else:
        first, later = rng.sample(small, 2)
        first_items, later_items = [first], [later]
        lines = [(first, 1), (later, 1)]
        method, carriers = method_for(rng, lines, customer["cc"], prefer="standard"), (CARRIERS["standard"],) * 2
        later_days = rng.randint(*STANDARD_DAYS[customer["cc"]])
    first_shipped = add_working_days(delivered, -rng.randint(*STANDARD_DAYS[customer["cc"]]))
    later_shipped = add_working_days(expected, -later_days)
    paying = pay_method(rng, customer, order_total(method, lines))
    placed, paid = placed_and_paid(rng, paying, min(first_shipped, later_shipped))
    parcels = [
        arrived(ctx, carriers[0], first_items, first_shipped, delivered),
        moving(ctx, carriers[1], later_items, later_shipped, expected),
    ]
    pay = payment(rng, paying, paid, min(first_shipped, later_shipped), today)
    order = assemble(customer, lines, method, placed, pay, parcels, status_of(parcels))
    slots = {
        "delivered_item": first_items[0]["short"],
        "missing_item": later_items[0]["short"],
        "delivered": when(rng, delivered, today),
    }
    articles = ["HC-06"] if method == "two-person" else None
    return Scenario(customer, slots, [date_fact(expected)], order, articles)


def sc_return_window(ctx: Ctx) -> Scenario:
    rng, today = ctx.rng, ctx.today
    customer = make_customer(rng, avoid=NO_LARGE_ITEMS)
    main = rng.choice(countable(products(avoid=("hygiene", "measure"))))
    lines = [(main, 1)] if "large" in main["flags"] else add_small_items(rng, [(main, 1)])
    method = method_for(rng, lines, customer["cc"])
    delivered = working_day_on_or_before(today - timedelta(days=rng.randint(3, 24)))
    shipped = add_working_days(delivered, -transit(rng, CARRIERS[method], customer["cc"]))
    order = one_parcel_order(ctx, customer, lines, method, shipped, delivered)
    reason = rng.choice(REASONS)
    slots = {"item": main["short"], "delivered": when(rng, delivered, today), "reason": reason}
    slots["Reason"] = reason[0].upper() + reason[1:]
    unopened = reason in ("I changed my mind", "my partner bought the same one")
    extras = [line for line in TICKETS["return_window"]["extras"] if unopened or "sealed" not in line]
    return Scenario(customer, slots, [date_fact(order["return_by"])], order, extras=extras)


def sc_return_policy(ctx: Ctx) -> Scenario:
    product = ctx.rng.choice(countable(products(avoid=("hygiene", "measure"))))
    slots = {"product": display(product), "item": product["short"]}
    return Scenario(make_customer(ctx.rng), slots, [duration_fact(30, "days")])


def sc_refund_status(ctx: Ctx) -> Scenario:
    rng, today = ctx.rng, ctx.today
    customer = make_customer(rng)
    main = rng.choice(countable(products(avoid=("large", "hygiene", "measure"))))
    lines = add_small_items(rng, [(main, 1)], most=1)
    method = method_for(rng, lines, customer["cc"])
    if rng.random() < 0.6:  # back at the warehouse, refund on its way
        received = add_working_days(working_day_on_or_after(today), -rng.randint(1, 4))
        issued = None
    else:
        issued = add_working_days(working_day_on_or_after(today), -rng.randint(1, 3))
        received = add_working_days(issued, -rng.randint(1, 4))
    requested = add_working_days(received, -rng.randint(2, 4))
    delivered = working_day_on_or_before(requested - timedelta(days=rng.randint(1, 12)))
    shipped = add_working_days(delivered, -transit(rng, CARRIERS[method], customer["cc"]))
    order = one_parcel_order(ctx, customer, lines, method, shipped, delivered, later=False)
    names = [main["name"]] if len(lines) > 1 and rng.random() < 0.6 else [product["name"] for product, _ in lines]
    add_return(order, names, requested, received=received, issued=issued)
    refund = order["return"]["refund"]
    facts = [amount_fact(refund["amount"]), date_fact(refund["issued_on"] or refund["expected_by"])]
    item = main["short"] if len(names) == 1 else "items"
    paid_by_card = order["payment"]["method"] == "card"
    extras = [line for line in TICKETS["refund_status"]["extras"] if paid_by_card or "card" not in line]
    return Scenario(customer, {"item": item, "sent": when(rng, requested, today)}, facts, order, extras=extras)


def sc_delivery_cost(ctx: Ctx) -> Scenario:
    rng = ctx.rng
    variant = rng.choices(["large", "small", "express"], weights=[4, 4, 2])[0]
    if variant == "large":
        customer = make_customer(rng, avoid=NO_LARGE_ITEMS)
        product = rng.choice(products(need=("large",)))
        facts, articles = [amount_fact("39.00")], ["HC-06"]
    elif variant == "express":
        customer = make_customer(rng, allowed=EXPRESS_COUNTRIES)
        product = rng.choice(countable(products(avoid=("large",))))
        facts, articles = [amount_fact("9.95")], None
    else:
        customer = make_customer(rng)
        product = rng.choice([p for p in countable(products(avoid=("large",))) if p["short"] != "candle"])
        facts, articles = [amount_fact("4.95"), amount_fact("75.00")], None
    slots = {"product": display(product), "item": product["short"], "city": customer["city"]}
    slots["country"] = customer["country"]
    return Scenario(customer, slots, facts, None, articles, bodies=f"bodies_{variant}")


def sc_cancel_shipped(ctx: Ctx) -> Scenario:
    rng, today = ctx.rng, ctx.today
    customer = make_customer(rng)
    main = rng.choice(countable(products(avoid=("large",))))
    lines = add_small_items(rng, [(main, 1)], most=1)
    method = method_for(rng, lines, customer["cc"])
    days = transit(rng, CARRIERS[method], customer["cc"])
    expected = add_working_days(working_day_on_or_after(today), rng.randint(0, min(2, days - 1)))
    order = one_parcel_order(ctx, customer, lines, method, add_working_days(expected, -days), expected=expected)
    slots = {"item": main["short"], "placed": when(rng, date.fromisoformat(order["placed_on"]), today)}
    return Scenario(customer, slots, [duration_fact(30, "days")], order)


def sc_invoice_copy(ctx: Ctx) -> Scenario:
    rng, today = ctx.rng, ctx.today
    customer = make_customer(rng, avoid=NO_LARGE_ITEMS)
    main = rng.choice(countable(CATALOGUE))
    lines = [(main, 1)] if "large" in main["flags"] else add_small_items(rng, [(main, 1)])
    method = method_for(rng, lines, customer["cc"])
    shipped = add_working_days(working_day_on_or_after(today), -rng.randint(1, 15))
    order = shipped_order(ctx, customer, lines, method, shipped)
    return Scenario(customer, {}, [date_fact(order["invoice"]["emailed_on"])], order)


def sc_account_locked(ctx: Ctx) -> Scenario:
    return Scenario(make_customer(ctx.rng), {}, [duration_fact(30, "minutes")])


def sc_pay_later_due(ctx: Ctx) -> Scenario:
    rng, today = ctx.rng, ctx.today
    customer = make_customer(rng, allowed=PAY_LATER_COUNTRIES)
    while True:
        main = rng.choice(countable(CATALOGUE))
        lines = [(main, 1)] if "large" in main["flags"] else add_small_items(rng, [(main, 1)])
        method = method_for(rng, lines, customer["cc"])
        if PAY_LATER_RANGE[0] <= order_total(method, lines) <= PAY_LATER_RANGE[1]:
            break
    shipped = add_working_days(working_day_on_or_after(today), -rng.randint(1, 18))
    placed = shipped - timedelta(days=rng.choice([0, 1, 2]))
    parcels = forward_parcels(ctx, customer["cc"], lines, method, shipped)
    pay = payment(rng, "Pay in 30 days", None, shipped, today)
    order = assemble(customer, lines, method, placed, pay, parcels, status_of(parcels))
    return Scenario(customer, {}, [date_fact(pay["due_on"])], order)


def sc_pay_later_limit(ctx: Ctx) -> Scenario:
    rng = ctx.rng
    customer = make_customer(rng)
    expensive = [p for p in CATALOGUE if p["price"] > PAY_LATER_RANGE[1]]
    product = rng.choice(expensive if rng.random() < 0.35 else [p for p in CATALOGUE if p["price"] >= 400])
    slots = {"product": display(product), "item": product["short"], "price": said(rng, product["price"])}
    slots["city"] = customer["city"]
    return Scenario(customer, slots, [amount_fact("1500.00")])


def sc_discount_minimum(ctx: Ctx) -> Scenario:
    rng = ctx.rng
    product = rng.choice(countable([p for p in CATALOGUE if p["price"] < 50]))
    basket = product["price"] * (2 if product["price"] * 2 < 50 and rng.random() < 0.4 else 1)
    slots = {"item": product["short"], "basket": said(rng, basket)}
    return Scenario(make_customer(rng), slots, [amount_fact("50.00")])


def sc_assembly_service(ctx: Ctx) -> Scenario:
    rng = ctx.rng
    customer = make_customer(rng, allowed=ASSEMBLY_COUNTRIES)
    product = rng.choice(countable(products(need=("flatpack",))))
    slots = {"item": product["short"], "product": display(product), "city": customer["city"]}
    return Scenario(customer, slots, [amount_fact("49.00")])


def sc_warranty_period(ctx: Ctx) -> Scenario:
    rng = ctx.rng
    product = rng.choice(countable(products(avoid=("hygiene", "measure"))))
    years = 5 if "frame" in product["flags"] else 2
    slots = {"item": product["short"], "product": display(product)}
    return Scenario(make_customer(rng), slots, [duration_fact(years, "years")])


def _recent_order(ctx: Ctx, customer: dict, *, main=None, most=2, later=True, card_only=False) -> dict:
    rng = ctx.rng
    main = main or rng.choice(countable(products(avoid=("large",))))
    lines = [(main, 1)] if "large" in main["flags"] else add_small_items(rng, [(main, 1)], most=most)
    method = method_for(rng, lines, customer["cc"])
    shipped = add_working_days(working_day_on_or_after(ctx.today), -rng.randint(1, 8))
    if card_only:
        placed = shipped - timedelta(days=rng.choice([0, 1]))
        parcels = forward_parcels(ctx, customer["cc"], lines, method, shipped)
        pay = payment(rng, "card", placed, shipped, ctx.today)
        return assemble(customer, lines, method, placed, pay, parcels, status_of(parcels))
    return shipped_order(ctx, customer, lines, method, shipped, later=later)


def sc_double_charge(ctx: Ctx) -> Scenario:
    customer = make_customer(ctx.rng, avoid=NO_LARGE_ITEMS)
    order = _recent_order(ctx, customer, card_only=True)
    return Scenario(customer, {"total": said(ctx.rng, Decimal(order["total"]))}, [], order)


def sc_refund_overdue(ctx: Ctx) -> Scenario:
    rng, today = ctx.rng, ctx.today
    customer = make_customer(rng)
    main = rng.choice(countable(products(avoid=("large", "hygiene", "measure"))))
    lines = add_small_items(rng, [(main, 1)], most=1)
    method = method_for(rng, lines, customer["cc"])
    received = working_day_on_or_before(today - timedelta(days=rng.randint(9, 16)))
    requested = add_working_days(received, -rng.randint(2, 4))
    delivered = working_day_on_or_before(requested - timedelta(days=rng.randint(1, 10)))
    shipped = add_working_days(delivered, -transit(rng, CARRIERS[method], customer["cc"]))
    order = one_parcel_order(ctx, customer, lines, method, shipped, delivered, later=False)
    add_return(order, [main["name"]], requested, received=received)
    return Scenario(customer, {"item": main["short"], "received": when(rng, received, today)}, [], order)


def sc_price_drop(ctx: Ctx) -> Scenario:
    rng = ctx.rng
    customer = make_customer(rng, avoid=NO_LARGE_ITEMS)
    main = rng.choice(countable([p for p in CATALOGUE if p["price"] >= 40]))
    order = _recent_order(ctx, customer, main=main, most=1)
    cut = min(main["price"] * Decimal("0.3"), Decimal(rng.choice([5, 10, 15, 20, 30, 50, 100, 150])))
    new = (main["price"] - cut).quantize(Decimal("1")) - (Decimal("0.05") if main["price"] < 100 else 0)
    slots = {"item": main["short"], "product": display(main), "old": said(rng, main["price"]), "new": said(rng, new)}
    slots["placed"] = when(rng, date.fromisoformat(order["placed_on"]), ctx.today)
    return Scenario(customer, slots, [], order)


def vat_number(rng: random.Random, cc: str) -> str:
    return "".join(str(rng.randrange(10)) if ch == "#" else ch for ch in VAT_FORMATS[cc])


def sc_invoice_correction(ctx: Ctx) -> Scenario:
    rng = ctx.rng
    company, cc = rng.choice(COMPANIES)
    customer = make_customer(rng, allowed=(cc,))
    order = _recent_order(ctx, customer, main=rng.choice(countable(products(avoid=("large",)))), most=2)
    return Scenario(customer, {"company": company, "vat": vat_number(rng, cc)}, [], order)


def sc_reminder_fee_dispute(ctx: Ctx) -> Scenario:
    rng, today = ctx.rng, ctx.today
    customer = make_customer(rng, allowed=PAY_LATER_COUNTRIES)
    main = rng.choice(countable(products(avoid=("large",))))
    lines = add_small_items(rng, [(main, 1)])
    method = method_for(rng, lines, customer["cc"])
    due = today - timedelta(days=rng.randint(15, 19))
    shipped = working_day_on_or_before(due - timedelta(days=30))
    due = shipped + timedelta(days=30)
    paid = due + timedelta(days=rng.randint(9, 12))
    placed = shipped - timedelta(days=rng.choice([0, 1]))
    parcels = forward_parcels(ctx, customer["cc"], lines, method, shipped)
    pay = {"method": "Pay in 30 days", "status": "paid", "paid_on": iso(paid), "due_on": iso(due), "refunded_on": None}
    pay["reminders"] = [
        {"sent_on": iso(due + timedelta(days=7)), "fee": "0.00"},
        {"sent_on": iso(due + timedelta(days=14)), "fee": f"{REMINDER_FEE:.2f}"},
    ]
    order = assemble(customer, lines, method, placed, pay, parcels, status_of(parcels))
    return Scenario(customer, {"paid": when(rng, paid, today)}, [], order)


def sc_lost_parcel(ctx: Ctx) -> Scenario:
    rng, today = ctx.rng, ctx.today
    customer = make_customer(rng)
    main = rng.choice(countable(products(avoid=("large",))))
    lines = add_small_items(rng, [(main, 1)], most=1)
    method = method_for(rng, lines, customer["cc"], prefer="standard")
    monday = today - timedelta(days=today.weekday())
    expected = monday - timedelta(days=7) + timedelta(days=rng.randint(0, 4))  # some day last week
    shipped = add_working_days(expected, -transit(rng, CARRIERS[method], customer["cc"]))
    order = one_parcel_order(ctx, customer, lines, method, shipped, expected=expected, stalled=True)
    return Scenario(customer, {"item": main["short"], "expected": when(rng, expected, today)}, [], order)


def _just_delivered(ctx: Ctx, customer: dict, main: dict, *, most=1, days=(0, 2)) -> tuple[dict, date]:
    rng = ctx.rng
    lines = [(main, 1)] if "large" in main["flags"] else add_small_items(rng, [(main, 1)], most=most)
    method = method_for(rng, lines, customer["cc"])
    delivered = working_day_on_or_before(ctx.today - timedelta(days=rng.randint(*days)))
    shipped = add_working_days(delivered, -transit(rng, CARRIERS[method], customer["cc"]))
    return one_parcel_order(ctx, customer, lines, method, shipped, delivered), delivered


def sc_damaged_item(ctx: Ctx) -> Scenario:
    rng = ctx.rng
    customer = make_customer(rng, avoid=NO_LARGE_ITEMS)
    main = rng.choice(countable(products(avoid=("hygiene", "measure"))))
    order, delivered = _just_delivered(ctx, customer, main)
    kind = "fragile" if "fragile" in main["flags"] else "flatpack" if "flatpack" in main["flags"] else "other"
    slots = {"item": main["short"], "Item": main["short"][0].upper() + main["short"][1:]}
    slots.update(damage=rng.choice(DAMAGES[kind]), delivered=when(rng, delivered, ctx.today))
    return Scenario(customer, slots, [], order)


def sc_wrong_item(ctx: Ctx) -> Scenario:
    rng = ctx.rng
    customer = make_customer(rng)
    name, ordered, received = rng.choice(WRONG_ITEM_SWAPS)
    main = next(p for p in CATALOGUE if p["name"] == name)
    order, _ = _just_delivered(ctx, customer, main, days=(0, 3))
    return Scenario(customer, {"ordered_item": ordered, "received_item": received}, [], order)


def sc_missing_parts_claim(ctx: Ctx) -> Scenario:
    rng = ctx.rng
    customer = make_customer(rng, avoid=NO_LARGE_ITEMS)
    main = rng.choice(countable(products(need=("flatpack",))))
    order, _ = _just_delivered(ctx, customer, main, days=(0, 6))
    part, verb, verb_past = rng.choice(PARTS)
    slots = {"item": main["short"], "part": part, "Part": part[0].upper() + part[1:], "verb": verb}
    slots["verb_past"] = verb_past
    return Scenario(customer, slots, [], order)


def sc_missed_two_person(ctx: Ctx) -> Scenario:
    rng, today = ctx.rng, ctx.today
    customer = make_customer(rng, avoid=NO_LARGE_ITEMS)
    main = rng.choice(products(need=("large",)))
    lines = [(main, 1)]
    slot_day = add_working_days(working_day_on_or_after(today), -rng.randint(1, 3))
    shipped = add_working_days(slot_day, -rng.randint(5, 10))
    hours = rng.choice(SLOTS)
    depot = (add_working_days(slot_day, -rng.randint(1, 2)), TRANSIT_EVENTS["Brookhaul"][2])
    paying = pay_method(rng, customer, order_total("two-person", lines))
    placed, paid = placed_and_paid(rng, paying, shipped)
    parcels = [parcel(ctx, CARRIERS["two-person"], [main], shipped, slot_day, slot=hours, update=depot)]
    pay = payment(rng, paying, paid, shipped, today)
    order = assemble(customer, lines, "two-person", placed, pay, parcels, status_of(parcels))
    slots = {"item": main["short"], "slot_hours": hours, "slot_day": when(rng, slot_day, today)}
    return Scenario(customer, slots, [], order)


def sc_return_pickup_missed(ctx: Ctx) -> Scenario:
    rng, today = ctx.rng, ctx.today
    customer = make_customer(rng, avoid=NO_LARGE_ITEMS)
    main = rng.choice(products(need=("large",)))
    lines = [(main, 1)]
    collection = add_working_days(working_day_on_or_after(today), -rng.randint(1, 4))
    requested = add_working_days(collection, -rng.randint(3, 6))
    delivered = working_day_on_or_before(requested - timedelta(days=rng.randint(2, 14)))
    shipped = add_working_days(delivered, -rng.randint(5, 10))
    order = one_parcel_order(ctx, customer, lines, "two-person", shipped, delivered, later=False)
    add_return(order, [main["name"]], requested, collection=collection)
    slots = {"item": main["short"], "Item": main["short"][0].upper() + main["short"][1:]}
    return Scenario(customer, {**slots, "collection": day_name(collection, today)}, [], order)


def sc_checkout_error(ctx: Ctx) -> Scenario:
    rng = ctx.rng
    product = rng.choice(countable(CATALOGUE))
    return Scenario(make_customer(rng), {"error": rng.choice(ERRORS), "item": product["short"]})


def sc_reset_link_invalid(ctx: Ctx) -> Scenario:
    return Scenario(make_customer(ctx.rng))


def sc_app_crash(ctx: Ctx) -> Scenario:
    return Scenario(make_customer(ctx.rng))


def sc_email_change_error(ctx: Ctx) -> Scenario:
    return Scenario(make_customer(ctx.rng))


def sc_discount_code_error(ctx: Ctx) -> Scenario:
    rng = ctx.rng
    basket = rng.choice([p["price"] for p in CATALOGUE if p["price"] >= 60]) + rng.choice([0, Decimal("19.95")])
    return Scenario(make_customer(rng), {"basket_high": said(rng, basket)})


def sc_legal_threat(ctx: Ctx) -> Scenario:
    rng, today = ctx.rng, ctx.today
    customer = make_customer(rng)
    main = rng.choice(countable(products(avoid=("large",))))
    lines = add_small_items(rng, [(main, 1)], most=1)
    method = method_for(rng, lines, customer["cc"], prefer="standard")
    expected = working_day_on_or_before(today - timedelta(days=rng.randint(10, 20)))
    shipped = add_working_days(expected, -transit(rng, CARRIERS[method], customer["cc"]))
    order = one_parcel_order(ctx, customer, lines, method, shipped, expected=expected, stalled=True)
    return Scenario(customer, {"item": main["short"]}, [], order)


def sc_data_deletion(ctx: Ctx) -> Scenario:
    return Scenario(make_customer(ctx.rng))


def sc_fraud(ctx: Ctx) -> Scenario:
    rng, today = ctx.rng, ctx.today
    customer = make_customer(rng, avoid=NO_LARGE_ITEMS)
    other_city = rng.choice([city for city in CITIES[customer["cc"]] if city != customer["city"]])
    delivered_to = {**customer, "city": other_city}
    main = rng.choice(countable(CATALOGUE))
    lines = [(main, 1)] if "large" in main["flags"] else add_small_items(rng, [(main, 1)], most=1)
    method = method_for(rng, lines, customer["cc"])
    shipped = working_day_on_or_before(today - timedelta(days=rng.choice([0, 1])))
    placed = shipped - timedelta(days=rng.choice([0, 1]))
    parcels = [
        moving(ctx, carrier, items, shipped, add_working_days(shipped, transit(rng, carrier, customer["cc"])))
        for carrier, items in parcel_groups(lines, method)
    ]
    pay = payment(rng, "card", placed, shipped, today)
    order = assemble(delivered_to, lines, method, placed, pay, parcels, status_of(parcels))
    slots = {"item": main["short"], "other_city": other_city, "total": said(rng, Decimal(order["total"]))}
    return Scenario(customer, slots, [], order)


def sc_safety(ctx: Ctx) -> Scenario:
    rng = ctx.rng
    customer = make_customer(rng, avoid=NO_LARGE_ITEMS)
    electric = rng.random() < 0.5
    pool = products(need=("electric",)) if electric else [p for p in CATALOGUE if p["sku"] in TIPPING_SKUS]
    main = rng.choice(pool)
    order, _ = _just_delivered(ctx, customer, main, days=(3, 40))
    return Scenario(
        customer, {"item": main["short"]}, [], order, bodies="bodies_electric" if electric else "bodies_tipping"
    )


TIPPING_SKUS = ("30301", "30501", "80101", "40213")  # wardrobe, bookcase, mirror, wall shelf


def sc_injection(ctx: Ctx) -> Scenario:
    rng = ctx.rng
    customer = make_customer(rng, avoid=NO_LARGE_ITEMS)
    order, _ = _just_delivered(ctx, customer, rng.choice(countable(CATALOGUE)), days=(2, 20))
    return Scenario(customer, {"total": said(rng, Decimal(order["total"]))}, [], order)


SCENARIOS = {name[3:]: function for name, function in list(globals().items()) if name.startswith("sc_")}


# ---------------------------------------------------------------- filler orders and past tickets


def filler_order(ctx: Ctx) -> dict:
    """An order nobody writes about, as it stands on the last day of the ticket window."""
    rng, today = ctx.rng, ctx.today
    customer = make_customer(rng)
    if customer["cc"] in NO_LARGE_ITEMS or rng.random() < 0.75:
        main = rng.choice(products(avoid=("large",)))
        lines = add_small_items(rng, [(main, 1)])
    else:
        lines = add_small_items(rng, [(rng.choice(products(need=("large",))), 1)], most=1)
    method = method_for(rng, lines, customer["cc"])
    placed = FIRST_ORDER_DAY + timedelta(days=rng.randint(0, (today - FIRST_ORDER_DAY).days))
    if rng.random() < 0.05:  # cancelled before it was packed
        refunded = placed + timedelta(days=rng.choice([0, 1]))
        pay = {"method": "card", "status": "refunded", "paid_on": iso(placed), "due_on": None}
        pay.update(refunded_on=iso(min(refunded, today)), reminders=[])
        return assemble(customer, lines, method, placed, pay, [], "cancelled")
    paying = pay_method(rng, customer, order_total(method, lines))
    if paying == "bank transfer" and (today - placed).days < 6:
        paying = "card"
    paid = add_working_days(placed, rng.choice([1, 2])) if paying == "bank transfer" else placed
    shipped = add_working_days(working_day_on_or_after(paid), rng.choice([0, 1]))
    if paying == "Pay in 30 days":
        paid = None
    if shipped > today:
        status = "received" if placed >= today - timedelta(days=1) else "packed"
        return assemble(customer, lines, method, placed, payment(rng, paying, paid, None, today), [], status)
    parcels = []
    for carrier, items in parcel_groups(lines, method):
        expected = add_working_days(shipped, transit(rng, carrier, customer["cc"]))
        if expected < today:
            parcels.append(arrived(ctx, carrier, items, shipped, expected))
        elif carrier == CARRIERS["standard"] and rng.random() < 0.2 and add_working_days(shipped, 1) < expected:
            first = add_working_days(expected, -1)
            parcels.append(moving(ctx, carrier, items, shipped, expected, first_expected=first))
        else:
            parcels.append(moving(ctx, carrier, items, shipped, expected))
    order = assemble(customer, lines, method, placed, payment(rng, paying, paid, shipped, today), parcels, "")
    order["status"] = status_of(parcels)
    if order["status"] == "delivered" and paying != "Pay in 30 days" and rng.random() < 0.15:
        _filler_return(ctx, order, lines)
    return order


def _filler_return(ctx: Ctx, order: dict, lines) -> None:
    rng, today = ctx.rng, ctx.today
    last_delivered = max(date.fromisoformat(p["delivered_on"]) for p in order["parcels"])
    latest = min(last_delivered + timedelta(days=28), today)
    if latest <= last_delivered:
        return
    requested = last_delivered + timedelta(days=rng.randint(1, (latest - last_delivered).days))
    product = rng.choice([p for p, _ in lines])
    names = [product["name"]] if len(lines) > 1 and rng.random() < 0.6 else [p["name"] for p, _ in lines]
    large = any("large" in p["flags"] for p, _ in lines if p["name"] in names)
    collection = collected = None
    if large:
        collection = add_working_days(requested, rng.randint(3, 6))
        if collection > today:
            add_return(order, names, requested, collection=collection)
            return
        collected = collection
        arrives = add_working_days(collection, rng.randint(1, 2))
    else:
        arrives = add_working_days(requested, rng.randint(2, 4))
    if arrives > today:
        add_return(order, names, requested, collection=collection, collected=collected)
        return
    expected_by = add_working_days(arrives, 5)
    issued = None
    if expected_by <= today:
        issued = add_working_days(arrives, rng.randint(1, working_days_between(arrives, expected_by)))
    add_return(order, names, requested, collection=collection, collected=collected, received=arrives, issued=issued)


def past_tickets(rng: random.Random) -> list[dict]:
    counts = {"routine": round(N_PAST * 0.6), "complex": round(N_PAST * 0.3)}
    counts["edge"] = N_PAST - sum(counts.values())
    kinds = []
    for category, names in (("routine", list(ROUTINE)), ("complex", list(COMPLEX)), ("edge", list(EDGE))):
        kinds += [(category, kind) for kind in allocate(rng, names, counts[category])]
    pairs: dict[str, list[tuple[str, str]]] = {}
    tickets = []
    for category, kind in kinds:
        subjects, messages, resolution = PAST[kind]
        if not pairs.get(kind):  # every distinct subject and message pair once before any repeats
            free = [
                line for key, lines in TICKETS[kind].items() if key != "extras" for line in lines if "{" not in line
            ]
            pool = [
                (s, m)
                for s in subjects + [f for f in free if len(f) < 50]
                for m in messages + [f for f in free if len(f) >= 50]
            ]
            rng.shuffle(pool)
            pairs[kind] = pool
        subject, message = pairs[kind].pop()
        if category == "routine":
            handled_by = "first-line support"
        elif category == "complex":
            handled_by = COMPLEX[kind][0]
        else:
            handled_by = "privacy team" if kind == "data_deletion" else "customer care lead"
        day = PAST_FIRST + timedelta(days=rng.randint(0, (PAST_LAST - PAST_FIRST).days))
        ticket = {"date": iso(day), "subject": subject, "message": message}
        tickets.append({**ticket, "resolution": resolution, "handled_by": handled_by})
    tickets.sort(key=lambda ticket: ticket["date"])
    return [{"id": f"PT-{number:04d}", **ticket} for number, ticket in enumerate(tickets, start=1)]


# ---------------------------------------------------------------- inbound tickets


def allocate(rng: random.Random, kinds: list[str], n: int) -> list[str]:
    """n kinds that cycle through every kind before repeating one, in a seeded order."""
    pool = list(kinds)
    rng.shuffle(pool)
    return [pool[index % len(pool)] for index in range(n)]


@dataclass
class Plan:
    category: str
    kind: str
    received: date
    time: str
    scenario: Scenario
    ticket_id: str = ""


def plan_split(rng: random.Random, n: int, taken: set[str]) -> list[Plan]:
    counts = {category: round(n * share) for category, share in MIX[:2]}
    counts["edge"] = n - sum(counts.values())
    kinds = []
    for category, names in (("routine", ROUTINE), ("complex", COMPLEX), ("edge", EDGE)):
        kinds += [(category, kind) for kind in allocate(rng, list(names), counts[category])]
    rng.shuffle(kinds)
    days = [FIRST_DAY + timedelta(days=offset) for offset in range((LAST_DAY - FIRST_DAY).days + 1)]
    weights = [1 if day.weekday() >= 5 else 4 for day in days]
    plans = []
    for category, kind in kinds:
        received = rng.choices(days, weights=weights)[0]
        time = f"{rng.choice(TIMES_OF_DAY)}:{rng.randrange(60):02d}"
        scenario = SCENARIOS[kind](Ctx(rng, received, taken))
        plans.append(Plan(category, kind, received, time, scenario))
    plans.sort(key=lambda plan: (plan.received, plan.time))
    return plans


def order_reference(rng: random.Random, order_id: str) -> dict:
    """How the customer writes the order number in this ticket: always the same way within one ticket."""
    digits, compact = order_id[3:], order_id.replace("-", "")
    forms = [
        f"order {order_id}",
        f"order {compact}",
        f"order #{digits}",
        f"order number {digits}",
        f"order no. {order_id}",
    ]
    written = rng.choice(forms)
    return {
        "order": written,
        "Order": written[0].upper() + written[1:],
        "Ref": rng.choice([order_id, f"#{digits}", compact]),
        "ref": order_id,
    }


def misspell(rng: random.Random, text: str) -> str:
    words = [word for word in TYPOS if re.search(rf"\b{word}\b", text)]
    if not words:
        return text
    word = rng.choice(words)
    return re.sub(rf"\b{word}\b", TYPOS[word], text, count=1)


def render(rng: random.Random, plan: Plan) -> str:
    spec, scenario = TICKETS[plan.kind], plan.scenario
    slots = dict(scenario.slots)
    if scenario.order:
        slots.update(order_reference(rng, scenario.order["order_id"]))
    subject_template, body_template = rng.choice(spec["subjects"]), rng.choice(spec[scenario.bodies])
    subject, sentences = subject_template.format_map(slots), [body_template.format_map(slots)]
    if scenario.order and not re.search(r"\{(?:order|Order|Ref|ref)\}", subject_template + body_template):
        sentences.append(f"{slots['Order']}.")  # the customer adds the order number at the end
    casual = False
    if plan.category != "edge":
        extras = spec["extras"] if scenario.extras is None else scenario.extras
        if extras and rng.random() < 0.5:
            sentences.append(rng.choice(extras).format_map(slots))
        chatty = [line for line in CHATTY if scenario.order or "order number" not in line]
        if rng.random() < 0.25:
            sentences.append(rng.choice(chatty))
        if rng.random() < 0.15:
            sentences[0] = misspell(rng, sentences[0])
        casual = rng.random() < 0.06
    body = " ".join(sentences)
    if casual:
        body = body.lower()
    customer = scenario.customer
    lines = [
        f"From: {customer['name']}",
        f"Received: {plan.received.isoformat()} {plan.time}",
        f"Subject: {subject}",
        "",
    ]
    if not casual and rng.random() < 0.85:
        lines += [rng.choice(GREETINGS), ""]
    lines += [body, "", rng.choice(SIGNOFFS).format(first=customer["first"], name=customer["name"])]
    return "\n".join(lines) + "\n"


def label_for(plan: Plan) -> dict:
    scenario = plan.scenario
    if plan.category == "edge":
        team, articles = "hold", list(EDGE[plan.kind])
    else:
        team, articles = (ROUTINE if plan.category == "routine" else COMPLEX)[plan.kind]
        articles = list(articles)
    articles += [article for article in scenario.articles or [] if article not in articles]
    return {
        "id": plan.ticket_id,
        "file": f"tickets/{plan.ticket_id}.txt",
        "received": plan.received.isoformat(),
        "category": plan.category,
        "kind": plan.kind,
        "expected_outcome": OUTCOME[plan.category],
        "team": team,
        "articles": articles,
        "key_facts": scenario.facts if plan.category == "routine" else [],
        "order_id": scenario.order["order_id"] if scenario.order else None,
        "edge": plan.kind if plan.category == "edge" else None,
    }


def number_orders(rng: random.Random, orders: list[dict]) -> None:
    """Order numbers grow with the order date, with gaps for the orders of customers who never write."""
    orders.sort(key=lambda order: order["placed_on"])
    number = 201000 + rng.randint(0, 900)
    for order in orders:
        number += rng.randint(3, 61)
        order["order_id"] = f"HV-{number}"


def build_dataset() -> dict:
    shop_rng, taken = random.Random(SHOP_SEED), set()
    plans = {}
    for split, (seed, n, prefix) in SPLITS.items():
        rng = random.Random(seed)
        plans[split] = (rng, plan_split(rng, n, taken))
        for number, plan in enumerate(plans[split][1], start=1):
            plan.ticket_id = f"{prefix}-{number:03d}"
    asked = [plan.scenario.order for _, split_plans in plans.values() for plan in split_plans if plan.scenario.order]
    filler_ctx = Ctx(shop_rng, LAST_DAY, taken)
    orders = asked + [filler_order(filler_ctx) for _ in range(N_ORDERS - len(asked))]
    number_orders(shop_rng, orders)
    data = {"articles": ARTICLES, "past_tickets": past_tickets(shop_rng), "orders": orders}
    for split, (rng, split_plans) in plans.items():
        data[split] = [
            {"id": plan.ticket_id, "text": render(rng, plan), "label": label_for(plan)} for plan in split_plans
        ]
    return data


# ---------------------------------------------------------------- files


def _jsonl(rows: list[dict]) -> str:
    return "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)


def all_files(data: dict | None = None) -> dict[str, str]:
    data = data or build_dataset()
    files = {
        "shop/help_centre.jsonl": _jsonl(data["articles"]),
        "shop/past_tickets.jsonl": _jsonl(data["past_tickets"]),
        "shop/orders.jsonl": _jsonl(data["orders"]),
    }
    for split in SPLITS:
        for ticket in data[split]:
            files[f"{split}/{ticket['label']['file']}"] = ticket["text"]
        files[f"{split}/labels.jsonl"] = _jsonl([ticket["label"] for ticket in data[split]])
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="compare with the committed files instead of writing")
    args = parser.parse_args()
    files = all_files()
    if args.check:
        stale = [
            path
            for path, content in files.items()
            if not (HERE / path).exists() or (HERE / path).read_text(encoding="utf-8") != content
        ]
        for path in stale:
            print(f"differs: data/{path}")
        print("data is up to date" if not stale else f"{len(stale)} file(s) differ: run `make data`")
        return 1 if stale else 0
    for path, content in files.items():
        target = HERE / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    print(f"wrote {len(files)} files under data/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
