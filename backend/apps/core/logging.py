"""Structured (JSON-lines) logging for Railway's stdout collector.

Every record is one JSON object: timestamp, level, logger, message and the request id. Only a fixed
set of fields is emitted — there is deliberately NO `extra` pass-through and no request/response
body, header or query string, so a stray `logger.info("...", extra={...})` cannot leak a credential.
Messages themselves must never contain secrets (see docs/SECURITY.md); a last-line redaction removes
obvious bearer tokens, JWTs and `token=` / `password=` pairs and e-mail addresses.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime

from apps.core.middleware import current_request_id

_BEARER = re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE)
_JWT = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*")
_PAIR = re.compile(
    r"""(["']?(?:access|refresh|token|password|authorization|secret|key)["']?\s*[:=]\s*)"""
    r"""("[^"]*"|'[^']*'|[^\s,}&]+)""",
    re.IGNORECASE,
)
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def redact(text: str) -> str:
    text = _BEARER.sub("Bearer [redacted]", text)
    text = _JWT.sub("[redacted-jwt]", text)
    text = _PAIR.sub(lambda m: f"{m.group(1)}[redacted]", text)
    return _EMAIL.sub("[redacted-email]", text)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": redact(record.getMessage()),
            "request_id": current_request_id(),
        }
        if record.exc_info:
            # The traceback goes to the log (never to the API client); redact it as well.
            entry["exc"] = redact(self.formatException(record.exc_info))
        return json.dumps(entry, ensure_ascii=False, separators=(",", ":"))
