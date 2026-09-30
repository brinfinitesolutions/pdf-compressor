from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)

_env_dir = os.getenv("DATA_DIR")
DATA_DIR = Path(_env_dir) if _env_dir else Path(__file__).resolve().parent.parent / "data"
MEDIA_PATH = DATA_DIR / "media.json"

_home_photo_id: str | None = None
_loaded = False


def _load() -> dict:
    try:
        return json.loads(MEDIA_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _save(payload: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix="media.", suffix=".json", dir=DATA_DIR)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
        Path(tmp_name).replace(MEDIA_PATH)
    except Exception:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def get_home_photo_id() -> str | None:
    global _home_photo_id, _loaded
    if _home_photo_id:
        return _home_photo_id
    if not _loaded:
        value = _load().get("home_photo_file_id")
        if isinstance(value, str) and value:
            _home_photo_id = value
        _loaded = True
    return _home_photo_id


def set_home_photo_id(file_id: str | None) -> None:
    global _home_photo_id, _loaded
    _loaded = True
    _home_photo_id = file_id or None
    payload = _load()
    if _home_photo_id:
        payload["home_photo_file_id"] = _home_photo_id
    else:
        payload.pop("home_photo_file_id", None)
    try:
        _save(payload)
    except OSError:
        log.exception("could not persist home photo file_id to %s", MEDIA_PATH)
