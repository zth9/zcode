"""Tool abstractions and built-in tools for zcode."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any

from .shell import run_command_with_limits


COMMAND_TIMEOUT_SECONDS = 120
# 这里只做最粗粒度的防呆，目标是避免明显危险命令被直接放行。
BLOCKED_COMMAND_SNIPPETS = (
    "rm -rf /",
    "sudo ",
    "shutdown",
    "reboot",
    "> /dev/",
)


class BaseTool(ABC):
    """Shared protocol for tools exposed to the model."""

    def __init__(self, name: str, description: str, input_schema: dict[str, Any]):
        self.name = name
        self.description = description
        self.input_schema = input_schema

    def to_tool_definition(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }

    @abstractmethod
    def run(self, tool_input: Any) -> str:
        """Execute the tool and return a text observation."""

    def format_trace(self, tool_input: Any) -> str:
        return f"[{self.name}] {tool_input}"


class BashTool(BaseTool):
    """Run shell commands inside the current workspace."""

    def __init__(self) -> None:
        super().__init__(
            name="bash",
            description="Run a shell command inside the current working directory.",
            input_schema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute.",
                    }
                },
                "required": ["command"],
            },
        )

    def run(self, tool_input: Any) -> str:
        if not isinstance(tool_input, dict):
            return "Error: Invalid input for bash tool; expected an object with a 'command' field"

        command = tool_input.get("command")
        if not isinstance(command, str) or not command.strip():
            return "Error: Invalid input for bash tool; 'command' must be a non-empty string"

        # 这个最小项目不做完整沙箱，只拦截最明显的高危片段。
        if any(snippet in command for snippet in BLOCKED_COMMAND_SNIPPETS):
            return "Error: Dangerous command blocked"

        result = run_command_with_limits(
            command=command,
            cwd=os.getcwd(),
            timeout_seconds=COMMAND_TIMEOUT_SECONDS,
        )
        return f"[exit_code={result.exit_code}]\n{result.output}"

    def format_trace(self, tool_input: Any) -> str:
        if isinstance(tool_input, dict) and isinstance(tool_input.get("command"), str):
            return f"$ {tool_input['command']}"
        return "$ <invalid command>"


def get_default_tools() -> list[BaseTool]:
    return [BashTool()]
