"""A very small made-up shop for unit tests: four articles, two past tickets, four orders."""

from datetime import date

from support_triage_agent.knowledge import KnowledgeBase

TICKET_DATE = date(2026, 10, 1)

ARTICLES = [
    {
        "id": "HC-04",
        "title": "Delivery times and costs",
        "section": "Delivery",
        "team": "logistics",
        "body": "Standard delivery with Veloway Parcel costs €4.95 and is free for orders over €75. "
        "Large items are delivered by Brookhaul two-person delivery for €39.00 per order.",
    },
    {
        "id": "HC-05",
        "title": "Tracking your parcel",
        "section": "Delivery",
        "team": "logistics",
        "body": "When your order ships, we email you the carrier's name and a tracking number. "
        "The expected delivery date is shown in My account > Orders.",
    },
    {
        "id": "HC-10",
        "title": "How to return an item",
        "section": "Returns and refunds",
        "team": "logistics",
        "body": "You can return most items within 30 days of delivery. A Brookhaul collection costs €29.00.",
    },
    {
        "id": "HC-11",
        "title": "When you get your refund",
        "section": "Returns and refunds",
        "team": "billing",
        "body": "We refund you within 5 working days after your return arrives at our warehouse.",
    },
]

PAST_TICKETS = [
    {
        "id": "PT-0001",
        "date": "2026-08-14",
        "subject": "Charged twice for one order",
        "message": "I can see two card payments for one order.",
        "resolution": "Billing checked with the card processor and released the duplicate authorisation.",
        "handled_by": "billing",
    },
    {
        "id": "PT-0002",
        "date": "2026-08-20",
        "subject": "Where is my parcel?",
        "message": "My parcel has not arrived yet, when will it come?",
        "resolution": "Closed by first-line support with the expected delivery date and the tracking number.",
        "handled_by": "first-line support",
    },
]


def _order(order_id, **fields):
    base = {
        "order_id": order_id,
        "placed_on": "2026-09-21",
        "customer": {"name": "Bram Visser", "city": "Utrecht", "country": "Netherlands"},
        "status": "shipped",
        "items": [{"sku": "40211", "name": "Ashby oak bedside table", "qty": 1, "unit_price": "89.00"}],
        "delivery": {"method": "standard", "cost": "0.00"},
        "total": "89.00",
        "payment": {"method": "card", "status": "paid", "paid_on": "2026-09-21"},
        "invoice": None,
        "parcels": [],
        "return_by": None,
        "return": None,
    }
    base.update(fields)
    return base


ORDERS = [
    _order(
        "HV-204518",
        items=[
            {"sku": "40211", "name": "Ashby oak bedside table", "qty": 1, "unit_price": "89.00"},
            {"sku": "51207", "name": "Linen cushion cover, sage", "qty": 1, "unit_price": "19.95"},
        ],
        total="108.95",
        invoice={"emailed_on": "2026-09-23"},
        parcels=[
            {
                "carrier": "Veloway Parcel",
                "tracking": "VW4829103746",
                "items": ["Ashby oak bedside table", "Linen cushion cover, sage"],
                "shipped_on": "2026-09-23",
                "expected_on": "2026-10-02",
                "first_expected_on": None,
                "delivered_on": None,
                "slot": None,
                "last_update": {"date": "2026-09-30", "event": "in transit to the local depot"},
            }
        ],
    ),
    _order(
        "HV-204777",
        status="delivered",
        items=[{"sku": "62210", "name": "Wool throw, mustard", "qty": 1, "unit_price": "49.90"}],
        delivery={"method": "standard", "cost": "4.95"},
        total="54.85",
        invoice={"emailed_on": "2026-09-17"},
        parcels=[
            {
                "carrier": "Veloway Parcel",
                "tracking": "VW1122334455",
                "items": ["Wool throw, mustard"],
                "shipped_on": "2026-09-17",
                "expected_on": "2026-09-20",
                "first_expected_on": None,
                "delivered_on": "2026-09-20",
                "slot": None,
                "last_update": {"date": "2026-09-20", "event": "delivered"},
            }
        ],
        return_by="2026-10-20",
    ),
    _order(
        "HV-203990",
        placed_on="2026-09-12",
        parcels=[
            {
                "carrier": "Veloway Parcel",
                "tracking": "VW5566778899",
                "items": ["Ashby oak bedside table"],
                "shipped_on": "2026-09-14",
                "expected_on": "2026-09-18",
                "first_expected_on": None,
                "delivered_on": None,
                "slot": None,
                "last_update": {"date": "2026-09-16", "event": "arrived at the sorting centre"},
            }
        ],
    ),
    _order(
        "HV-205001",
        status="return in progress",
        items=[{"sku": "62210", "name": "Wool throw, mustard", "qty": 1, "unit_price": "49.90"}],
        delivery={"method": "standard", "cost": "4.95"},
        total="54.85",
        parcels=[
            {
                "carrier": "Veloway Parcel",
                "tracking": "VW9988776655",
                "items": ["Wool throw, mustard"],
                "shipped_on": "2026-09-15",
                "expected_on": "2026-09-18",
                "first_expected_on": None,
                "delivered_on": "2026-09-18",
                "slot": None,
                "last_update": {"date": "2026-09-18", "event": "delivered"},
            }
        ],
        return_by="2026-10-18",
        **{
            "return": {
                "items": ["Wool throw, mustard"],
                "requested_on": "2026-09-22",
                "received_on": "2026-09-25",
                "collection_on": None,
                "collected_on": None,
                "refund": {"amount": "49.90", "status": "processing", "expected_by": "2026-10-02", "issued_on": None},
            }
        },
    ),
]


def shop() -> KnowledgeBase:
    return KnowledgeBase(ARTICLES, PAST_TICKETS, ORDERS)
