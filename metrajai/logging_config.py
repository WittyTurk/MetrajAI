from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(log_dir: str | Path) -> Path:
    target_dir = Path(log_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "engine.jsonl"
    handler = logging.FileHandler(target, encoding="utf-8")
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger("metrajai")
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    return target
