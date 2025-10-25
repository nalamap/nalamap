"""
Test JSON serialization helper for streaming endpoint
"""

import os
import sys

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

# Import the function we want to test
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from api.nalamap import make_json_serializable  # noqa: E402


def test_make_json_serializable_with_human_message():
    """Test that HumanMessage objects are serialized correctly"""
    msg = HumanMessage(content="Hello world")
    result = make_json_serializable(msg)

    assert result == {"type": "human", "content": "Hello world"}


def test_make_json_serializable_with_ai_message():
    """Test that AIMessage objects are serialized correctly"""
    msg = AIMessage(content="Hi there!")
    result = make_json_serializable(msg)

    assert result == {"type": "ai", "content": "Hi there!"}


def test_make_json_serializable_with_system_message():
    """Test that SystemMessage objects are serialized correctly"""
    msg = SystemMessage(content="System prompt")
    result = make_json_serializable(msg)

    assert result == {"type": "system", "content": "System prompt"}


def test_make_json_serializable_with_list_of_messages():
    """Test that lists containing messages are serialized correctly"""
    messages = [
        HumanMessage(content="Question"),
        AIMessage(content="Answer"),
    ]
    result = make_json_serializable(messages)

    assert result == [
        {"type": "human", "content": "Question"},
        {"type": "ai", "content": "Answer"},
    ]


def test_make_json_serializable_with_dict_containing_messages():
    """Test that dicts containing messages are serialized correctly"""
    data = {
        "query": "test",
        "messages": [HumanMessage(content="Hello")],
        "count": 1,
    }
    result = make_json_serializable(data)

    assert result == {
        "query": "test",
        "messages": [{"type": "human", "content": "Hello"}],
        "count": 1,
    }


def test_make_json_serializable_with_nested_structures():
    """Test deeply nested structures with messages"""
    data = {
        "conversation": {
            "messages": [
                HumanMessage(content="Q1"),
                AIMessage(content="A1"),
            ],
            "metadata": {
                "user": "test",
                "nested_msg": SystemMessage(content="sys"),
            },
        }
    }
    result = make_json_serializable(data)

    assert result["conversation"]["messages"] == [
        {"type": "human", "content": "Q1"},
        {"type": "ai", "content": "A1"},
    ]
    assert result["conversation"]["metadata"]["nested_msg"] == {"type": "system", "content": "sys"}


def test_make_json_serializable_with_primitives():
    """Test that primitive types pass through unchanged"""
    assert make_json_serializable("string") == "string"
    assert make_json_serializable(123) == 123
    assert make_json_serializable(45.67) == 45.67
    assert make_json_serializable(True) is True
    assert make_json_serializable(None) is None


def test_make_json_serializable_with_empty_structures():
    """Test empty lists and dicts"""
    assert make_json_serializable([]) == []
    assert make_json_serializable({}) == {}


def test_make_json_serializable_with_non_serializable_object():
    """Test that non-JSON-serializable objects are converted to strings"""

    class CustomObject:
        def __str__(self):
            return "CustomObject instance"

    obj = CustomObject()
    result = make_json_serializable(obj)

    assert result == "CustomObject instance"
