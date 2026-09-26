from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncio

    from signalbot import LinkPreview


@dataclass
class BroadcastContent:
    message: str
    attachments: list[str] | None
    link_preview: LinkPreview | None
    view_once: bool | None


@dataclass
class BroadcastState:
    subscriber_uuid: str
    action_str: str
    acting_str: str
    num_subscribers: int = -1
    broadcast_timestamps: dict[str, int] = field(default_factory=dict)
    send_tasks: list[tuple[str, asyncio.Task[int]]] = field(default_factory=list)
    send_tasks_checked: bool = False
    attachments_deleted: bool = False
    timestamp_data_saved: bool = False
