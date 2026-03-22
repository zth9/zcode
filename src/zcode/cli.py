"""CLI runtime for zcode."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any, Sequence

from anthropic import Anthropic
from dotenv import load_dotenv

from .agent import agent_loop


REPL_PROMPT = "\033[36mzcode >> \033[0m"
EXIT_COMMANDS = {"q", "quit", "exit"}


def load_client() -> tuple[Anthropic, str]:
    """Build the Anthropic-compatible client from environment variables."""
    load_dotenv(override=True)

    model = os.getenv("MODEL_ID")
    if not model:
        raise RuntimeError("Missing MODEL_ID in environment")

    base_url = os.getenv("ANTHROPIC_BASE_URL") or None
    auth_token = os.getenv("ANTHROPIC_AUTH_TOKEN") or None
    api_key = os.getenv("ANTHROPIC_API_KEY") or None

    client_kwargs: dict[str, Any] = {"base_url": base_url}
    if auth_token:
        client_kwargs["auth_token"] = auth_token
    elif api_key:
        client_kwargs["api_key"] = api_key
    else:
        raise RuntimeError("Missing ANTHROPIC_AUTH_TOKEN or ANTHROPIC_API_KEY")

    return Anthropic(**client_kwargs), model


def is_repl_exit(query: str) -> bool:
    normalized = query.strip().lower()
    return not normalized or normalized in EXIT_COMMANDS


def extract_text(content: Sequence[Any]) -> str:
    texts: list[str] = []
    for block in content:
        if getattr(block, "type", None) == "text" and getattr(block, "text", None):
            texts.append(block.text)
    return "\n".join(texts).strip()


def run_once(
    client: Anthropic,
    model: str,
    prompt: str,
    history: list[dict[str, Any]] | None = None,
) -> str:
    messages = history if history is not None else []
    # REPL 会复用整段 history；如果本轮失败，需要把现场回滚干净。
    start_len = len(messages)
    messages.append({"role": "user", "content": prompt})
    try:
        content = agent_loop(client, model, messages)
    except Exception:
        del messages[start_len:]
        raise
    return extract_text(content)


def repl(client: Anthropic, model: str) -> int:
    history: list[dict[str, Any]] = []
    while True:
        try:
            query = input(REPL_PROMPT)
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if is_repl_exit(query):
            return 0

        try:
            answer = run_once(client, model, query.strip(), history)
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr)
            continue

        if answer:
            print(answer)
        print()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the minimal zcode agent loop.")
    parser.add_argument("prompt", nargs="*", help="Optional one-shot prompt")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    client, model = load_client()
    if args.prompt:
        prompt = " ".join(args.prompt).strip()
        if not prompt:
            return 0
        answer = run_once(client, model, prompt)
        if answer:
            print(answer)
        return 0
    return repl(client, model)
