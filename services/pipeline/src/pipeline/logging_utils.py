"""Structured JSON-lines logging for the pipeline.

Standing privacy rule: raw docket text, defendant-identifying data, and file
contents must NEVER be logged — not here, not in tests, not in CI. Log only
metadata: counts, durations, filenames-by-hash or batch IDs, and error types.

Named ``logging_utils`` (not ``logging``) to avoid shadowing the stdlib module.
Logs go to stderr so stdout stays free for machine-readable command output.
"""

import json
import logging
import sys
from datetime import UTC, datetime

# Attributes present on every stdlib LogRecord; anything else on a record was
# passed via ``extra=`` and belongs in the JSON output.
_STANDARD_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message",
    "asctime",
}


class JSONFormatter(logging.Formatter):
    """Format each record as a single JSON object on one line."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and key not in entry:
                entry[key] = value
        return json.dumps(entry, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    """Attach a JSON-lines stderr handler to the root logger.

    Replaces any existing root handlers so repeated calls (e.g. across tests)
    don't duplicate output.
    """
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JSONFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
