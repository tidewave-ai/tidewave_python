import hashlib
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Optional

cwd = os.getcwd()
digest = hashlib.md5(cwd.encode("utf-8")).hexdigest()[:16]

temp_dir = Path(tempfile.gettempdir())
log_file = temp_dir / f"{digest}.tidewave.log"

file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

logging.getLogger().addHandler(file_handler)


def get_logs(tail: int, *, grep: Optional[str] = None) -> str:
    """
    Returns all log output, excluding logs that were caused by other tool calls.

    Use this tool to check for request logs or potentially logged errors.

    Arguments:
      * `tail`: The number of log entries to return from the end of the log
      * `grep`: Filter logs with the given regular expression (case insensitive)
        E.g. "error" when you want to capture errors in particular
    """
    if not log_file.exists():
        return ""

    try:
        # Read all lines from the log file
        with open(log_file, encoding="utf-8") as f:
            lines = f.readlines()

        # Apply grep filter if provided
        if grep:
            try:
                regex = re.compile(grep, re.IGNORECASE)
                lines = [line for line in lines if regex.search(line)]
            except re.error as e:
                return f"Invalid regular expression '{grep}': {e}"

        # Get the last 'tail' lines
        if tail <= 0:
            return "Tail parameter must be a positive integer"

        selected_lines = lines[-tail:] if len(lines) > tail else lines

        # Join and return the lines
        result = "".join(selected_lines)

        if not result.strip():
            if grep:
                return f"No log entries found matching pattern '{grep}'"
            else:
                return "No log entries found"

        return result

    except Exception as e:
        return f"Error reading log file: {e}"
