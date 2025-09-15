import hashlib
import logging
import os
import re
import tempfile
from collections import deque
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

    if tail <= 0:
        return "Tail parameter must be a positive integer"

    try:
        regex = None
        if grep:
            try:
                regex = re.compile(grep, re.IGNORECASE)
            except re.error as e:
                return f"Invalid regular expression '{grep}': {e}"

        # Use deque to keep only last `tail` lines.
        tail_lines = deque(maxlen=tail)

        with open(log_file, encoding="utf-8") as f:
            if regex:
                for line in filter(regex.search, f):
                    tail_lines.append(line)
            else:
                for line in f:
                    tail_lines.append(line)

        # Join and return the lines
        result = "".join(tail_lines).strip()

        if not result:
            if grep:
                return f"No log entries found matching pattern '{grep}'"
            else:
                return "No log entries found"

        return result

    except Exception as e:
        return f"Error reading log file: {e}"
