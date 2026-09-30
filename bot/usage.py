from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from bot.media_store import DATA_DIR

log = logging.getLogger(__name__)

USAGE_PATH = DATA_DIR / "usage.json"
DAILY_FILE_LIMIT = 5
DAILY_BYTE_LIMIT = 10 * 1024 * 1024


def unlimited_chat_ids() -> set[int]:
    raw = os.getenv("UNLIMITED_CHAT_IDS", "")
    ids: set[int] = set()
    for part in raw.replace(";", ",").split(","):
        token = part.strip()
        if not token:
            continue
        try:
            ids.add(int(token))
        except ValueError:
            log.warning("ignoring invalid UNLIMITED_CHAT_IDS entry: %s", token)
    return ids


def is_unlimited(chat_id: int, user_id: int | None = None) -> bool:
    allowed = unlimited_chat_ids()
    if chat_id in allowed:
        return True
    return user_id is not None and user_id in allowed


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _load() -> dict:
    try:
        return json.loads(USAGE_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"users": {}}


def _save(payload: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix="usage.", suffix=".json", dir=DATA_DIR)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
        Path(tmp_name).replace(USAGE_PATH)
    except Exception:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def _record_for(user_id: int) -> dict:
    payload = _load()
    users = payload.setdefault("users", {})
    rec = users.get(str(user_id)) or {}
    if rec.get("date") != _today():
        rec = {"date": _today(), "files": 0, "bytes": 0}
    rec.setdefault("files", 0)
    rec.setdefault("bytes", 0)
    return rec


def would_exceed(user_id: int, extra_bytes: int) -> bool:
    rec = _record_for(user_id)
    if rec["files"] >= DAILY_FILE_LIMIT:
        return True
    if rec["bytes"] >= DAILY_BYTE_LIMIT:
        return True
    if rec["files"] + 1 > DAILY_FILE_LIMIT:
        return True
    if rec["bytes"] + max(0, extra_bytes) > DAILY_BYTE_LIMIT:
        return True
    return False


def record_file(user_id: int, extra_bytes: int) -> None:
    payload = _load()
    users = payload.setdefault("users", {})
    rec = _record_for(user_id)
    rec["files"] = int(rec.get("files", 0)) + 1
    rec["bytes"] = int(rec.get("bytes", 0)) + max(0, extra_bytes)
    rec["date"] = _today()
    users[str(user_id)] = rec
    try:
        _save(payload)
    except OSError:
        log.exception("could not persist daily usage to %s", USAGE_PATH)
