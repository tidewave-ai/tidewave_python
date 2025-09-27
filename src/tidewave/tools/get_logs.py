import hashlib
import logging
import os
import re
import tempfile
from collections import deque
from pathlib import Path
from typing import Optional


# Same as logging.Formatter, but strips any ANSI escape sequences.
class ColorlessFormatter(logging.Formatter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    def format(self, record):
        formatted = super().format(record)
        return self.ansi_escape.sub("", formatted)


cwd = os.getcwd()
digest = hashlib.md5(cwd.encode("utf-8")).hexdigest()[:16]

temp_dir = Path(tempfile.gettempdir())
log_file = temp_dir / f"{digest}.tidewave.log"


file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(
    ColorlessFormatter("%(name)s : %(asctime)s - %(levelname)s - %(message)s")
)


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
        raise ValueError("Tail parameter must be a positive integer")

    regex = None
    if grep:
        try:
            regex = re.compile(grep, re.IGNORECASE)
        except re.error as e:
            raise ValueError(f"Invalid regular expression '{grep}': {e}") from e

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
