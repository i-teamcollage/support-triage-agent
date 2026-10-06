import re
import sys
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "data"))

import generate  # noqa: E402

from support_triage_agent.agent import TEAMS  # noqa: E402
from support_triage_agent.facts import fact_stated  # noqa: E402
from support_triage_agent.knowledge import attention, find_order_ids, render_order  # noqa: E402
from support_triage_agent.ticket import Ticket  # noqa: E402

DATA = generate.build_dataset()
ARTICLES = {article["id"]: article for article in DATA["articles"]}
ORDERS = {order["order_id"]: order for order in DATA["orders"]}
SPLITS = {"practice": DATA["practice"], "test": DATA["test"]}
TICKETS = [ticket for tickets in SPLITS.values() for ticket in tickets]
ASKED_ABOUT = {ticket["label"]["order_id"]: ticket["label"] for ticket in TICKETS if ticket["label"]["order_id"]}
CARRIER_PREFIX = {"Veloway Parcel": ("VW", 10), "Tramline Couriers": ("TC", 9), "Brookhaul": ("BH", 8)}


def iso(value):
    return date.fromisoformat(value) if value else None


def labels(split):
    return [ticket["label"] for ticket in SPLITS[split]]


def snapshot(order):
    """The day an order record describes: the day its ticket arrived, or the last day of the window."""
    label = ASKED_ABOUT.get(order["order_id"])
    return iso(label["received"]) if label else generate.LAST_DAY


def add_working_days(day, n):
    while n:
        day += timedelta(days=1)
        n -= day.weekday() < 5
    return day


def test_the_help_centre_has_25_articles():
    assert list(ARTICLES) == [f"HC-{n:02d}" for n in range(1, 26)]
    for article in ARTICLES.values():
        assert article["title"] and article["section"] and article["body"], article["id"]
        assert article["team"] in TEAMS, article["id"]


def test_past_tickets_are_200_resolved_cases_that_say_who_handled_them():
    past = DATA["past_tickets"]
    assert [ticket["id"] for ticket in past] == [f"PT-{n:04d}" for n in range(1, 201)]
    assert [ticket["date"] for ticket in past] == sorted(ticket["date"] for ticket in past)
    assert all(iso(ticket["date"]) < generate.FIRST_DAY for ticket in past)
    handled = Counter(ticket["handled_by"] for ticket in past)
    assert set(handled) <= {"first-line support", *TEAMS, "customer care lead", "privacy team"}
    assert 100 <= handled["first-line support"] <= 140
    assert all(ticket["subject"] and ticket["message"] and ticket["resolution"] for ticket in past)


def test_the_orders_database_holds_300_orders_numbered_in_date_order():
    orders = DATA["orders"]
    assert len(orders) == len(ORDERS) == 300
    assert all(re.fullmatch(r"HV-\d{6}", order["order_id"]) for order in orders)
    assert [order["order_id"] for order in orders] == sorted(ORDERS)
    assert [order["placed_on"] for order in orders] == sorted(order["placed_on"] for order in orders)


def test_order_totals_add_up():
    for order in DATA["orders"]:
        items = sum(Decimal(item["unit_price"]) * item["qty"] for item in order["items"])
        assert items + Decimal(order["delivery"]["cost"]) == Decimal(order["total"]), order["order_id"]


def test_delivery_follows_the_help_centre():
    for order in DATA["orders"]:
        large = any(item["sku"] in generate.LARGE_SKUS for item in order["items"])
        method, cost = order["delivery"]["method"], Decimal(order["delivery"]["cost"])
        items = Decimal(order["total"]) - cost
        assert (method == "two-person") == large, order["order_id"]
        if method == "two-person":
            assert cost == Decimal("39.00")
            assert order["customer"]["country"] != "Ireland", order["order_id"]
        elif method == "express":
            assert cost == Decimal("9.95")
            assert order["customer"]["country"] in ("Netherlands", "Belgium", "Germany"), order["order_id"]
        else:
            assert cost == (Decimal("0.00") if items > 75 else Decimal("4.95")), order["order_id"]


def test_tracking_numbers_match_their_carrier_and_are_unique():
    seen = []
    for order in DATA["orders"]:
        for parcel in order["parcels"]:
            prefix, digits = CARRIER_PREFIX[parcel["carrier"]]
            assert re.fullmatch(rf"{prefix}\d{{{digits}}}", parcel["tracking"]), order["order_id"]
            seen.append(parcel["tracking"])
    assert len(seen) == len(set(seen))


def test_order_dates_follow_each_other():
    for order in DATA["orders"]:
        placed, parcels = iso(order["placed_on"]), order["parcels"]
        for parcel in parcels:
            shipped = iso(parcel["shipped_on"])
            assert placed <= shipped <= iso(parcel["expected_on"]), order["order_id"]
            if parcel["delivered_on"]:
                assert shipped <= iso(parcel["delivered_on"]), order["order_id"]
        if parcels:
            assert order["invoice"] == {"emailed_on": min(parcel["shipped_on"] for parcel in parcels)}
        else:
            assert order["invoice"] is None, order["order_id"]
        delivered = [iso(parcel["delivered_on"]) for parcel in parcels if parcel["delivered_on"]]
        if parcels and len(delivered) == len(parcels):
            assert iso(order["return_by"]) == max(delivered) + timedelta(days=30), order["order_id"]
        else:
            assert order["return_by"] is None, order["order_id"]


def test_the_status_matches_the_parcels():
    for order in DATA["orders"]:
        status, parcels = order["status"], order["parcels"]
        delivered = sum(bool(parcel["delivered_on"]) for parcel in parcels)
        assert status in generate.STATUSES, order["order_id"]
        if status in ("received", "packed", "cancelled"):
            assert not parcels, order["order_id"]
        elif status in ("shipped", "delayed"):
            assert parcels and not delivered, order["order_id"]
            assert (status == "delayed") == any(parcel["first_expected_on"] for parcel in parcels), order["order_id"]
        elif status == "partly delivered":
            assert 0 < delivered < len(parcels), order["order_id"]
        else:
            assert parcels and delivered == len(parcels), order["order_id"]
        assert (status in ("return in progress", "returned")) <= bool(order["return"]), order["order_id"]


def test_payments_follow_the_help_centre():
    for order in DATA["orders"]:
        payment, placed = order["payment"], order["placed_on"]
        shipped = min((parcel["shipped_on"] for parcel in order["parcels"]), default=None)
        if payment["method"] == "card":
            assert payment["paid_on"] == placed, order["order_id"]
        elif payment["method"] == "bank transfer":
            assert placed <= payment["paid_on"] and (shipped is None or payment["paid_on"] <= shipped)
        else:
            assert payment["method"] == "Pay in 30 days", order["order_id"]
            country = order["customer"]["country"]
            assert country in ("Netherlands", "Belgium", "Germany", "Austria"), order["order_id"]
            assert Decimal("20") <= Decimal(order["total"]) <= Decimal("1500"), order["order_id"]
            assert order["return"] is None, order["order_id"]
            if shipped:
                assert iso(payment["due_on"]) == iso(shipped) + timedelta(days=30), order["order_id"]
        if order["status"] == "cancelled" and payment["method"] != "Pay in 30 days":
            assert payment["status"] == "refunded" and payment["refunded_on"] >= placed, order["order_id"]


def test_refunds_add_up():
    for order in DATA["orders"]:
        returned = order["return"]
        if not returned:
            continue
        prices = {item["name"]: Decimal(item["unit_price"]) * item["qty"] for item in order["items"]}
        expected = sum(prices[name] for name in returned["items"])
        if returned["collection_on"]:
            expected -= Decimal("29.00")
        if set(returned["items"]) == set(prices) and order["delivery"]["method"] != "two-person":
            expected += Decimal(order["delivery"]["cost"])
        refund = returned["refund"]
        assert iso(returned["requested_on"]) <= iso(order["return_by"]), order["order_id"]
        if returned["received_on"]:
            assert iso(returned["requested_on"]) <= iso(returned["received_on"]), order["order_id"]
        if refund:
            assert Decimal(refund["amount"]) == expected, order["order_id"]
            assert iso(refund["expected_by"]) == add_working_days(iso(returned["received_on"]), 5), order["order_id"]
            if refund["status"] == "issued":
                assert iso(returned["received_on"]) <= iso(refund["issued_on"]) <= iso(refund["expected_by"])


def test_no_order_record_shows_something_that_had_not_happened_yet():
    for order in DATA["orders"]:
        day = snapshot(order).isoformat()
        happened = [order["placed_on"], order["payment"].get("paid_on"), order["payment"].get("refunded_on")]
        happened += [reminder["sent_on"] for reminder in order["payment"].get("reminders") or []]
        happened += [(order["invoice"] or {}).get("emailed_on")]
        for parcel in order["parcels"]:
            happened += [parcel["shipped_on"], parcel["delivered_on"], parcel["last_update"]["date"]]
        returned = order["return"] or {}
        happened += [returned.get(key) for key in ("requested_on", "received_on", "collected_on")]
        happened += [(returned.get("refund") or {}).get("issued_on")]
        assert all(value <= day for value in happened if value), order["order_id"]


def test_orders_nobody_asks_about_have_nothing_overdue():
    for order in DATA["orders"]:
        if order["order_id"] not in ASKED_ABOUT:
            assert attention(order, generate.LAST_DAY) == [], order["order_id"]


def test_each_split_has_the_promised_size_and_mix():
    for split, sizes in (("practice", (50, 30, 15, 5)), ("test", (100, 60, 30, 10))):
        found = Counter(label["category"] for label in labels(split))
        assert (len(labels(split)), found["routine"], found["complex"], found["edge"]) == sizes


def test_the_same_seeds_give_the_same_data():
    again = generate.build_dataset()
    assert [ticket["text"] for ticket in again["test"]] == [ticket["text"] for ticket in DATA["test"]]
    assert again["orders"] == DATA["orders"]


def test_the_practice_split_covers_every_routine_and_edge_kind_and_every_team():
    practice = labels("practice")
    assert {label["kind"] for label in practice if label["category"] == "routine"} == set(generate.ROUTINE)
    assert {label["kind"] for label in practice if label["category"] == "edge"} == set(generate.EDGE)
    assert {label["team"] for label in practice if label["category"] == "complex"} == set(TEAMS)


def test_labels_follow_the_category():
    outcome = {"routine": "close", "complex": "route", "edge": "hold"}
    for label in labels("practice") + labels("test"):
        assert label["expected_outcome"] == outcome[label["category"]], label["id"]
        if label["category"] == "edge":
            assert (label["team"], label["edge"]) == ("hold", label["kind"]), label["id"]
        else:
            assert label["team"] in TEAMS and label["edge"] is None, label["id"]
        assert all(article_id in ARTICLES for article_id in label["articles"]), label["id"]
        if label["category"] == "routine":
            assert label["articles"] and label["key_facts"], label["id"]
        else:
            assert label["key_facts"] == [], label["id"]


def test_ticket_headers_carry_the_sender_the_date_and_the_subject():
    for split, tickets in SPLITS.items():
        prefix = split[0]
        assert [ticket["id"] for ticket in tickets] == [f"{prefix}-{n:03d}" for n in range(1, len(tickets) + 1)]
        received = [re.search(r"Received: (.+)", ticket["text"]).group(1) for ticket in tickets]
        assert received == sorted(received), "ticket ids follow the order of arrival"
        for ticket in tickets:
            parsed = Ticket.parse(ticket["id"], ticket["text"])
            assert parsed.received.isoformat() == ticket["label"]["received"], ticket["id"]
            assert generate.FIRST_DAY <= parsed.received <= generate.LAST_DAY, ticket["id"]
            assert parsed.sender and parsed.subject, ticket["id"]
            assert "{" not in ticket["text"] and "}" not in ticket["text"], ticket["id"]


def test_a_ticket_names_exactly_its_own_order_and_that_order_exists():
    for ticket in TICKETS:
        order_id = ticket["label"]["order_id"]
        assert find_order_ids(ticket["text"]) == ([order_id] if order_id else []), ticket["id"]
        assert order_id is None or order_id in ORDERS, ticket["id"]


def test_each_order_belongs_to_at_most_one_ticket():
    named = [ticket["label"]["order_id"] for ticket in TICKETS if ticket["label"]["order_id"]]
    assert len(named) == len(set(named))


def test_the_key_facts_of_a_routine_ticket_are_in_its_order_or_a_relevant_article():
    for ticket in TICKETS:
        label = ticket["label"]
        if label["category"] != "routine":
            continue
        received = iso(label["received"])
        sources = [ARTICLES[article_id]["body"] for article_id in label["articles"]]
        if label["order_id"]:
            sources.append(render_order(ORDERS[label["order_id"]], received))
        for fact in label["key_facts"]:
            assert any(fact_stated(fact, source, received.year) for source in sources), (label["id"], fact)


def test_routine_orders_have_nothing_overdue_when_the_ticket_arrives():
    for ticket in TICKETS:
        label = ticket["label"]
        if label["category"] == "routine" and label["order_id"]:
            assert attention(ORDERS[label["order_id"]], iso(label["received"])) == [], label["id"]


def test_late_and_missed_deliveries_show_in_the_order_record():
    late_kinds = {"lost_parcel", "refund_overdue", "missed_two_person", "return_pickup_missed"}
    found = 0
    for ticket in TICKETS:
        label = ticket["label"]
        if label["kind"] in late_kinds:
            found += 1
            assert attention(ORDERS[label["order_id"]], iso(label["received"])), label["id"]
    assert found >= 4


def test_every_file_lands_where_the_agent_reads_it():
    files = generate.all_files(DATA)
    assert {"shop/help_centre.jsonl", "shop/past_tickets.jsonl", "shop/orders.jsonl"} <= set(files)
    for split, tickets in SPLITS.items():
        assert files[f"{split}/labels.jsonl"].count("\n") == len(tickets)
        for ticket in tickets:
            assert files[f"{split}/{ticket['label']['file']}"] == ticket["text"]
