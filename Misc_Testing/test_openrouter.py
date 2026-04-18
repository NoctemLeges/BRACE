"""
Smoke test for the OpenRouter migration.
Tests: (1) basic completion, (2) schema generation, (3) tool calling loop.

Usage: python test_openrouter.py
"""
import json
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Code_For_LLM_Server.llm_client import LLMClient, Chat, function_to_tool_schema


# ── Test 1: Basic text completion ──────────────────────────────────────

def test_basic_completion():
    print("=== Test 1: Basic text completion ===")
    model = LLMClient()
    chat = Chat("You are a helpful assistant. Be very brief.")
    chat.add_user_message("What is 2 + 2? Reply with just the number.")
    result = model.respond(chat)
    print(f"Response: {result}")
    assert "4" in result, f"Expected '4' in response, got: {result}"
    print("PASS\n")


# ── Test 2: Schema generation ──────────────────────────────────────────

def test_schema_generation():
    print("=== Test 2: Schema generation ===")

    def add_numbers(a: int, b: int) -> int:
        """Add two numbers together.

        Args:
            a: First number.
            b: Second number.

        Returns:
            The sum of a and b.
        """
        return a + b

    schema = function_to_tool_schema(add_numbers)
    print(json.dumps(schema, indent=2))

    assert schema["function"]["name"] == "add_numbers"
    assert schema["function"]["parameters"]["properties"]["a"]["type"] == "integer"
    assert schema["function"]["parameters"]["properties"]["b"]["type"] == "integer"
    assert "a" in schema["function"]["parameters"]["required"]
    assert "b" in schema["function"]["parameters"]["required"]
    print("PASS\n")


# ── Test 3: Tool calling loop ──────────────────────────────────────────

def test_tool_calling():
    print("=== Test 3: Tool calling loop ===")

    def get_weather(city: str) -> str:
        """Get the current weather for a city.

        Args:
            city: The city name to check weather for.

        Returns:
            A string describing the weather.
        """
        print(f"  [tool called] get_weather(city={city!r})")
        return f"The weather in {city} is sunny, 72°F."

    model = LLMClient()
    chat = Chat("You have a weather tool. Use it when asked about weather.")
    chat.add_user_message("What's the weather in San Francisco?")
    result = model.act(
        chat,
        [get_weather],
        on_content=lambda c: print(f"  [assistant] {c}"),
    )
    print(f"Final response: {result}")
    assert result is not None, "act() returned None — max iterations reached"
    print("PASS\n")


# ── Run all tests ─────────────────────────────────────────────────────

if __name__ == "__main__":
    test_basic_completion()
    test_schema_generation()
    test_tool_calling()
    print("All tests passed!")
