"""Core agent loop and model/tool orchestration."""

from __future__ import annotations

import os
from typing import Any, Sequence

from anthropic import Anthropic

from .tools import BaseTool, get_default_tools


DEFAULT_MAX_TOKENS = 4096
MAX_TOOL_ROUNDS = 20
TRACE_PREVIEW_LENGTH = 200


def build_system_prompt(workspace: str | None = None) -> str:
    current_workspace = workspace or os.getcwd()
    return (
        "You are zcode, a minimal CLI coding agent running in "
        f"{current_workspace}. Use the available tools to inspect the "
        "workspace and solve tasks. Act directly, keep responses concise, "
        "and stop when the task is done."
    )


def request_turn(
    client: Anthropic,
    model: str,
    messages: list[dict[str, Any]],
    tool_definitions: list[dict[str, Any]],
) -> Any:
    response = client.messages.create(
        model=model,
        system=build_system_prompt(),
        messages=messages,
        tools=tool_definitions,
        max_tokens=DEFAULT_MAX_TOKENS,
    )
    messages.append({"role": "assistant", "content": response.content})
    return response


def build_tool_registry() -> dict[str, BaseTool]:
    return {tool.name: tool for tool in get_default_tools()}


def format_tool_error(tool_name: str, exc: Exception) -> str:
    return f"Error: Tool '{tool_name}' failed: {exc.__class__.__name__}: {exc}"


def print_tool_trace(label: str, output: str) -> None:
    print(f"\033[33m{label}\033[0m")
    preview = output[:TRACE_PREVIEW_LENGTH]
    print(preview)
    if len(output) > len(preview):
        print("...")


def execute_tool_call(block: Any, tool_registry: dict[str, BaseTool]) -> dict[str, str]:
    tool_name = getattr(block, "name", None)
    if not tool_name:
        raise RuntimeError("Tool call missing tool name")

    tool = tool_registry.get(tool_name)
    if tool is None:
        raise RuntimeError(f"Unknown tool requested: {tool_name}")

    tool_input = getattr(block, "input", None)
    try:
        # trace 只是调试输出，格式化失败也不能影响工具真正执行。
        trace_label = tool.format_trace(tool_input)
    except Exception as exc:
        trace_label = f"[{tool_name}] <trace failed: {exc.__class__.__name__}: {exc}>"

    try:
        output = tool.run(tool_input)
    except Exception as exc:
        output = format_tool_error(tool_name, exc)

    print_tool_trace(trace_label, output)
    return {"type": "tool_result", "tool_use_id": block.id, "content": str(output)}


def collect_tool_results(
    content: Sequence[Any], tool_registry: dict[str, BaseTool]
) -> list[dict[str, str]]:
    # 模型可能在一轮里提出多个 tool_use，这里统一执行后再整体回填。
    tool_results = [
        execute_tool_call(block, tool_registry)
        for block in content
        if getattr(block, "type", None) == "tool_use"
    ]
    if not tool_results:
        raise RuntimeError("Model requested tool_use but returned no tool calls")
    return tool_results


def agent_loop(client: Anthropic, model: str, messages: list[dict[str, Any]]) -> Sequence[Any]:
    tool_registry = build_tool_registry()
    tool_definitions = [tool.to_tool_definition() for tool in tool_registry.values()]
    for _ in range(MAX_TOOL_ROUNDS):
        response = request_turn(client, model, messages, tool_definitions)
        if response.stop_reason != "tool_use":
            return response.content
        # Anthropic 协议要求把 tool_result 作为一条 user 消息送回下一轮。
        messages.append(
            {"role": "user", "content": collect_tool_results(response.content, tool_registry)}
        )
    raise RuntimeError(f"Exceeded the maximum tool rounds ({MAX_TOOL_ROUNDS})")
