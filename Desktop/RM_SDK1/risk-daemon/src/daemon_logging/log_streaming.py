"""
Real-time log streaming for CLI admin tool.

Provides tail -f style log following with JSON parsing and human-readable formatting.

Architecture Reference: architecture/20-logging-framework.md
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Optional


async def stream_logs(
    log_file: Path, category: str = "all", tail: int = 10
) -> AsyncGenerator[str, None]:
    """
    Stream log entries from a log file in real-time.

    Similar to `tail -f`, this function:
    1. Reads last N lines initially (tail parameter)
    2. Follows file for new entries
    3. Parses JSON and formats for human reading
    4. Filters by category if specified

    Args:
        log_file: Path to log file to stream
        category: Category filter ("all", "system", "enforcement", etc.)
        tail: Number of existing lines to read initially

    Yields:
        Formatted log lines (human-readable)

    Example:
        async for line in stream_logs(Path("system.log"), category="all", tail=20):
            print(line)
    """
    # Handle nonexistent file
    if not log_file.exists():
        raise FileNotFoundError(f"Log file not found: {log_file}")

    # Read initial lines (tail)
    initial_lines = await _read_last_n_lines(log_file, tail)

    for line in initial_lines:
        formatted = _parse_and_format_log_line(line, category)
        if formatted:
            yield formatted

    # Follow file for new entries
    last_position = log_file.stat().st_size

    while True:
        await asyncio.sleep(0.1)  # Poll interval

        # Check if file has grown
        try:
            current_size = log_file.stat().st_size
        except FileNotFoundError:
            # File might have been rotated
            break

        if current_size > last_position:
            # Read new content
            with open(log_file, "r", encoding="utf-8") as f:
                f.seek(last_position)
                new_lines = f.read()

            last_position = current_size

            # Process new lines
            for line in new_lines.strip().split("\n"):
                if line:
                    formatted = _parse_and_format_log_line(line, category)
                    if formatted:
                        yield formatted


async def _read_last_n_lines(log_file: Path, n: int) -> list[str]:
    """
    Read last N lines from a log file.

    Args:
        log_file: Path to log file
        n: Number of lines to read

    Returns:
        List of last N lines
    """
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Return last N lines
        return lines[-n:] if len(lines) > n else lines

    except FileNotFoundError:
        return []


def _parse_and_format_log_line(line: str, category_filter: str) -> Optional[str]:
    """
    Parse JSON log line and format for human reading.

    Args:
        line: JSON log line
        category_filter: Category filter ("all" or specific category)

    Returns:
        Formatted string or None if filtered out/invalid
    """
    try:
        # Parse JSON
        log_entry = json.loads(line.strip())

        # Apply category filter
        entry_category = log_entry.get("category", "system")
        if category_filter != "all" and entry_category != category_filter:
            return None

        # Format timestamp
        timestamp_str = log_entry.get("timestamp", "")
        if timestamp_str:
            try:
                dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                formatted_timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                formatted_timestamp = timestamp_str
        else:
            formatted_timestamp = "????-??-?? ??:??:??"

        # Format level (pad to 8 characters)
        level = log_entry.get("level", "INFO").ljust(8)

        # Format category (pad to 12 characters)
        category = entry_category.ljust(12)

        # Build formatted message
        parts = [f"[{formatted_timestamp}]", level, "|", category]

        # Add account_id if present
        if "account_id" in log_entry:
            parts.extend(["|", log_entry["account_id"]])

        # Add message
        message = log_entry.get("message", "")
        parts.extend(["|", message])

        return " ".join(parts)

    except json.JSONDecodeError:
        # Skip invalid JSON lines
        return None
    except Exception:
        # Skip any other parsing errors
        return None
