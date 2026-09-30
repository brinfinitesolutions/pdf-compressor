from __future__ import annotations

import json
import os
from io import BytesIO
from pathlib import Path

import requests
from dotenv import load_dotenv
from PIL import Image

from bot.welcome import LOGO_PATH

PROFILE_SIZE = 640


def _jpeg_profile_photo(path: Path) -> bytes:
    with Image.open(path) as opened:
        image = opened.convert("RGB")
        image.thumbnail((PROFILE_SIZE, PROFILE_SIZE), Image.Resampling.LANCZOS)
        buf = BytesIO()
        image.save(buf, format="JPEG", quality=92)
        return buf.getvalue()


START_COMMAND = {"command": "start", "description": "Open BR Infinite Compressor"}
COMPRESS_COMMAND = {"command": "compress", "description": "Compress an image or PDF"}
DEFAULT_COMMANDS = [
    START_COMMAND,
    COMPRESS_COMMAND,
    {"command": "cancel", "description": "Discard the current file"},
    {"command": "help", "description": "How to use BR Infinite Compressor"},
]


def _api(token: str, method: str, **kwargs) -> dict:
    response = requests.post(
        f"https://api.telegram.org/bot{token}/{method}",
        timeout=60,
        **kwargs,
    )
    payload = response.json()
    if not payload.get("ok"):
        raise SystemExit(f"{method} failed: {payload}")
    return payload


def _ensure_commands(token: str) -> None:
    current = _api(token, "getMyCommands").get("result") or []
    by_name = {item["command"]: item for item in current if item.get("command")}
    missing = [item["command"] for item in DEFAULT_COMMANDS if item["command"] not in by_name]
    if not missing:
        print("Bot command list is already up to date.")
        return
    for wanted in DEFAULT_COMMANDS:
        by_name.setdefault(wanted["command"], wanted)
    ordered = []
    seen: set[str] = set()
    for wanted in DEFAULT_COMMANDS:
        ordered.append(by_name[wanted["command"]])
        seen.add(wanted["command"])
    ordered.extend(cmd for name, cmd in by_name.items() if name not in seen)
    _api(token, "setMyCommands", data={"commands": json.dumps(ordered)})
    print("Updated bot commands: " + ", ".join(f"/{name}" for name in missing))


def main() -> None:
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token or token == "your-bot-token-from-botfather":
        raise SystemExit("Set TELEGRAM_BOT_TOKEN in .env before running make init-bot")
    if not LOGO_PATH.is_file():
        raise SystemExit(f"Logo not found: {LOGO_PATH}")

    jpeg = _jpeg_profile_photo(LOGO_PATH)
    _api(
        token,
        "setMyProfilePhoto",
        data={"photo": json.dumps({"type": "static", "photo": "attach://logo"})},
        files={"logo": ("br-logo.jpg", jpeg, "image/jpeg")},
    )
    print("Bot profile photo updated from the BR Infinite Solutions logo.")
    _ensure_commands(token)


if __name__ == "__main__":
    main()
