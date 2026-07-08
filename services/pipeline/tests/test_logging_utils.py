import json
import logging

from pipeline.logging_utils import JSONFormatter, configure_logging


def make_record(msg: str, args: tuple = ()) -> logging.LogRecord:
    return logging.LogRecord(
        name="pipeline.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=args,
        exc_info=None,
    )


def test_formatter_emits_expected_fields():
    entry = json.loads(JSONFormatter().format(make_record("hello %s", ("world",))))
    assert entry["level"] == "INFO"
    assert entry["logger"] == "pipeline.test"
    assert entry["message"] == "hello world"
    assert "timestamp" in entry


def test_formatter_output_is_single_line():
    formatted = JSONFormatter().format(make_record("one line"))
    assert "\n" not in formatted


def test_extra_fields_included(capsys):
    configure_logging()
    logging.getLogger("pipeline.test").info(
        "batch complete", extra={"batch_id": "b-123", "count": 4}
    )
    entry = json.loads(capsys.readouterr().err.strip())
    assert entry["batch_id"] == "b-123"
    assert entry["count"] == 4
    assert entry["message"] == "batch complete"
