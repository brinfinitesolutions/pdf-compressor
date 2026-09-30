from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Kind = Literal["image", "pdf"]
State = Literal["await_size", "await_custom", "await_format"]
Unit = Literal["kb", "mb"]


@dataclass
class Session:
    user_id: int
    chat_id: int
    original_path: str
    original_name: str
    kind: Kind
    original_size: int
    state: State
    source_message_id: int
    prompt_message_id: int
    custom_unit: Unit | None = None
    target_bytes: int | None = None
    compressed_path: str | None = None
    compressed_size: int | None = None
    under_target: bool = True


_sessions: dict[int, Session] = {}
_inbox: dict[int, tuple[int, int]] = {}


def get(user_id: int) -> Session | None:
    return _sessions.get(user_id)


def put(session: Session) -> Session:
    _sessions[session.user_id] = session
    return session


def clear(user_id: int) -> Session | None:
    return _sessions.pop(user_id, None)


def set_inbox(user_id: int, chat_id: int, message_id: int) -> None:
    _inbox[user_id] = (chat_id, message_id)


def pop_inbox(user_id: int) -> tuple[int, int] | None:
    return _inbox.pop(user_id, None)
