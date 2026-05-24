"""Structured audit logging (spec §3.6, §7.3).

Emits one JSON line per audited event. Under ``audience: minors`` the platform logs
aggregate only — per-student identifiers are dropped (spec §7.2). The platform
itself ships no log viewer; a separate consumer tool reads this stream.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger("ensayo.audit")

_PII_FIELDS = ("student_id", "student_email", "email", "name")


def audit(event: str, *, audience: str = "adults", **fields) -> None:
    if audience == "minors":
        for k in _PII_FIELDS:
            fields.pop(k, None)
    logger.info(json.dumps(
        {"ts": datetime.now(timezone.utc).isoformat(), "event": event, **fields}))
