"""How tool calls are written for Ollama. This is the only file that knows the format.

The request lists the tools in the OpenAI-style function format. When the model asks for tools, the
conversation gets the assistant's request back, followed by one "tool" message per call with the
result as plain text. If a live smoke test shows the model expects another shape, change it here.
"""

from __future__ import annotations

from typing import Any

from .llm import ToolCall


def _tool(name: str, description: str, parameter: str, parameter_description: str) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {parameter: {"type": "string", "description": parameter_description}},
                "required": [parameter],
            },
        },
    }


TOOLS: list[dict[str, Any]] = [
    _tool(
        "search_help_centre",
        "Search the Hollinvale Home help centre: 25 articles on orders, delivery, returns, refunds, payments, "
        "invoices, products and accounts. Returns the 3 best articles with their ids and full text.",
        "query",
        "A few words that describe the customer's question, for example: refund after return",
    ),
    _tool(
        "search_past_tickets",
        "Search 200 past tickets to see how similar requests were handled and by which team. "
        "Returns the 3 best matches.",
        "query",
        "A few words that describe the customer's problem",
    ),
    _tool(
        "lookup_order",
        "Look up one order by its number. Returns status, items, totals, payment, invoice, parcels with "
        "tracking numbers and dates, the return window, and any return or refund.",
        "order_id",
        "The order number, for example HV-123456",
    ),
]


def tool_turn(text: str, calls: list[ToolCall], results: list[str]) -> list[dict[str, Any]]:
    """The messages to append after the model asked for tools: its request, then one result per call."""
    assistant = {
        "role": "assistant",
        "content": text,
        "tool_calls": [{"function": {"name": call.name, "arguments": call.arguments}} for call in calls],
    }
    return [
        assistant,
        *[
            {"role": "tool", "tool_name": call.name, "content": result}
            for call, result in zip(calls, results, strict=True)
        ],
    ]
