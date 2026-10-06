from support_triage_agent.llm import ToolCall
from support_triage_agent.ollama_tools import TOOLS, tool_turn


def test_tools_use_the_function_format_ollama_expects():
    assert [tool["type"] for tool in TOOLS] == ["function", "function", "function"]
    names = [tool["function"]["name"] for tool in TOOLS]
    assert names == ["search_help_centre", "search_past_tickets", "lookup_order"]
    for tool in TOOLS:
        function = tool["function"]
        assert function["description"]
        assert function["parameters"]["type"] == "object"
        assert function["parameters"]["required"] == list(function["parameters"]["properties"])


def test_a_tool_turn_is_the_assistant_request_then_one_tool_message_per_call():
    calls = [ToolCall("lookup_order", {"order_id": "HV-204518"}), ToolCall("search_help_centre", {"query": "late"})]
    messages = tool_turn("Let me check.", calls, ["Order HV-204518 ...", "Help centre ..."])
    assert messages == [
        {
            "role": "assistant",
            "content": "Let me check.",
            "tool_calls": [
                {"function": {"name": "lookup_order", "arguments": {"order_id": "HV-204518"}}},
                {"function": {"name": "search_help_centre", "arguments": {"query": "late"}}},
            ],
        },
        {"role": "tool", "tool_name": "lookup_order", "content": "Order HV-204518 ..."},
        {"role": "tool", "tool_name": "search_help_centre", "content": "Help centre ..."},
    ]
