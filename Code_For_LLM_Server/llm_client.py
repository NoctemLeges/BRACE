import inspect
import json
import re
import time
import typing
from openai import OpenAI, RateLimitError

try:
    from .llm_config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, DEFAULT_MODEL
except ImportError:
    from llm_config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, DEFAULT_MODEL


def _python_type_to_json_schema(annotation) -> dict:
    """Convert a Python type annotation to a JSON Schema type."""
    if annotation is inspect.Parameter.empty or annotation is None:
        return {"type": "string"}

    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)

    if annotation is str:
        return {"type": "string"}
    elif annotation is int:
        return {"type": "integer"}
    elif annotation is float:
        return {"type": "number"}
    elif annotation is bool:
        return {"type": "boolean"}
    elif origin is list:
        items = _python_type_to_json_schema(args[0]) if args else {"type": "string"}
        return {"type": "array", "items": items}
    elif origin is dict:
        return {"type": "object"}
    else:
        return {"type": "string"}


def _parse_docstring_args(docstring: str) -> tuple[str, dict[str, str]]:
    """Extract the description and per-parameter descriptions from a docstring.

    Returns (description, {param_name: param_description}).
    """
    if not docstring:
        return "", {}

    lines = docstring.strip().split("\n")

    # Everything before "Args:" is the description
    desc_lines = []
    arg_descriptions = {}
    in_args = False
    current_param = None

    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith("args:"):
            in_args = True
            continue
        if stripped.lower().startswith("returns:"):
            in_args = False
            continue

        if in_args:
            # Match "param_name: description" or "param_name (type): description"
            match = re.match(r"(\w+)(?:\s*\([^)]*\))?\s*:\s*(.*)", stripped)
            if match:
                current_param = match.group(1)
                arg_descriptions[current_param] = match.group(2).strip()
            elif current_param and stripped:
                # Continuation line for the current parameter
                arg_descriptions[current_param] += " " + stripped
        else:
            if stripped:
                desc_lines.append(stripped)

    description = " ".join(desc_lines)
    return description, arg_descriptions


def function_to_tool_schema(func) -> dict:
    """Convert a Python function into an OpenAI-format tool schema.

    The function must have type hints and a docstring with an Args: section.
    """
    sig = inspect.signature(func)
    description, arg_descs = _parse_docstring_args(func.__doc__ or "")

    properties = {}
    required = []

    for name, param in sig.parameters.items():
        prop = _python_type_to_json_schema(param.annotation)
        if name in arg_descs:
            prop["description"] = arg_descs[name]
        properties[name] = prop

        if param.default is inspect.Parameter.empty:
            required.append(name)

    schema = {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
            },
        },
    }
    if required:
        schema["function"]["parameters"]["required"] = required

    return schema


class Chat:
    """Simple chat message list wrapper, compatible with OpenAI's message format."""

    def __init__(self, system_prompt: str):
        self.messages: list[dict] = [{"role": "system", "content": system_prompt}]

    def add_user_message(self, content: str):
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str):
        self.messages.append({"role": "assistant", "content": content})

    def add_tool_result(self, tool_call_id: str, content: str):
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content,
        })

    def append(self, message: dict):
        """Append a raw message dict."""
        self.messages.append(message)


class LLMClient:
    """OpenRouter LLM client with text completion and tool-calling support."""

    def __init__(self, model: str | None = None):
        self.model = model or DEFAULT_MODEL
        self.client = OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=OPENROUTER_API_KEY,
        )

    def _create_with_retry(self, **kwargs):
        """Call chat.completions.create with retry on rate limit (429)."""
        max_retries = 5
        for attempt in range(max_retries):
            try:
                return self.client.chat.completions.create(**kwargs)
            except RateLimitError:
                if attempt == max_retries - 1:
                    raise
                wait = 10 * (attempt + 1)
                print(f"  [rate limited, retrying in {wait}s...]")
                time.sleep(wait)

    def respond(self, chat: Chat) -> str:
        """Plain text completion. No tools. Returns the content string."""
        response = self._create_with_retry(
            model=self.model,
            messages=chat.messages,
        )
        content = response.choices[0].message.content or ""
        chat.add_assistant_message(content)
        return content

    def act(self, chat: Chat, tools: list, on_content=None, max_iterations: int = 10) -> str | None:
        """Tool-calling loop.

        Sends messages with tool schemas, executes any tool calls the model makes,
        appends results, and repeats until the model responds without tool calls.

        Args:
            chat: The conversation to continue.
            tools: List of Python functions to expose as tools.
            on_content: Callback(str) called with assistant text content.
            max_iterations: Safety limit on loop iterations.

        Returns:
            The final assistant text response, or None if max_iterations reached.
        """
        tool_schemas = [function_to_tool_schema(t) for t in tools]
        tool_map = {t.__name__: t for t in tools}

        for _ in range(max_iterations):
            response = self._create_with_retry(
                model=self.model,
                messages=chat.messages,
                tools=tool_schemas,
                tool_choice="auto",
            )
            msg = response.choices[0].message

            # Build assistant message dict
            assistant_msg: dict = {"role": "assistant", "content": msg.content or ""}
            if msg.tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ]
            chat.append(assistant_msg)

            if msg.content and on_content:
                on_content(msg.content)

            # No tool calls — we're done
            if not msg.tool_calls:
                return msg.content or ""

            # Execute each tool call
            for tc in msg.tool_calls:
                func_name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                func = tool_map.get(func_name)
                if func is None:
                    result = f"Error: unknown tool '{func_name}'"
                else:
                    try:
                        result = func(**args)
                    except Exception as e:
                        result = f"Error calling {func_name}: {e}"

                if not isinstance(result, str):
                    result = json.dumps(result)

                chat.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })

        return None
