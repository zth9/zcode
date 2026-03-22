"""Shell execution helpers for workspace tools."""

from __future__ import annotations

import selectors
import subprocess
import time
from dataclasses import dataclass


OUTPUT_LIMIT = 50_000
READ_CHUNK_SIZE = 4096


@dataclass
class CommandResult:
    exit_code: int
    output: str
    truncated: bool = False


def decode_output(raw: bytes) -> str:
    return raw.decode("utf-8", errors="replace")


def run_command_with_limits(
    command: str,
    cwd: str,
    timeout_seconds: int,
    max_output_bytes: int = OUTPUT_LIMIT,
) -> CommandResult:
    process = subprocess.Popen(
        command,
        shell=True,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        executable="/bin/bash",
    )
    selector = selectors.DefaultSelector()
    stdout_chunks: list[bytes] = []
    stderr_chunks: list[bytes] = []
    captured_bytes = 0
    output_truncated = False
    deadline = time.monotonic() + timeout_seconds

    if process.stdout is not None:
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    if process.stderr is not None:
        selector.register(process.stderr, selectors.EVENT_READ, "stderr")

    try:
        # 同时消费 stdout/stderr，避免单边缓冲区塞满把子进程卡住。
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                process.kill()
                process.wait()
                return CommandResult(
                    exit_code=-1,
                    output=f"Error: Timeout ({timeout_seconds}s)",
                )

            events = selector.select(timeout=remaining)
            if not events:
                if process.poll() is not None:
                    break
                continue

            for key, _ in events:
                stream = key.fileobj
                chunk = stream.read1(READ_CHUNK_SIZE)
                if not chunk:
                    selector.unregister(stream)
                    stream.close()
                    continue

                remaining_bytes = max_output_bytes - captured_bytes
                if remaining_bytes > 0:
                    kept = chunk[:remaining_bytes]
                    if key.data == "stdout":
                        stdout_chunks.append(kept)
                    else:
                        stderr_chunks.append(kept)
                    captured_bytes += len(kept)

                # 到达输出上限后主动终止，防止无界输出拖垮会话。
                if not output_truncated and captured_bytes >= max_output_bytes:
                    output_truncated = True
                    process.kill()

        exit_code = process.wait()
    finally:
        selector.close()

    combined = decode_output(b"".join(stdout_chunks) + b"".join(stderr_chunks)).strip()
    if not combined:
        combined = "(no output)"
    if output_truncated:
        combined = (
            f"{combined}\n\n"
            f"[output truncated to {max_output_bytes} bytes; process terminated]"
        )
    return CommandResult(exit_code=exit_code, output=combined, truncated=output_truncated)
