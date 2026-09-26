import json
import logging
import sys
from datetime import UTC, datetime


class EventFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        event: dict[str, object] = {
            "time": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "event": record.getMessage(),
        }
        for field in (
            "request_id", "run_id", "method", "status", "duration_ms",
            "error_code", "error_type", "input_tokens", "output_tokens",
        ):
            value = getattr(record, field, None)
            if value is not None:
                event[field] = value
        return json.dumps(event, ensure_ascii=False)


def configure_logging() -> None:
    for name in ("open_tennis", "app"):
        logger = logging.getLogger(name)
        if not any(isinstance(handler.formatter, EventFormatter) for handler in logger.handlers):
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(EventFormatter())
            logger.addHandler(handler)
        logger.setLevel(logging.INFO)
