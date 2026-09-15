"""session_watch 单元测试：会话消息同步水位与任务终态唤醒。"""

import asyncio
from typing import Any, List, cast
from unittest.mock import AsyncMock, patch

from src.ai_rpg.models import SessionMessage, SessionMessageResponse
from src.ai_rpg.tui import session_watch
from src.ai_rpg.tui.server_client import (
    _notify_task_succeeded,
    add_task_succeeded_listener,
    remove_task_succeeded_listener,
)


class _FakeSession:
    def __init__(self, user: str = "u", game: str = "g") -> None:
        self.user_name = user
        self.game_name = game
        self.last_sequence_id = 0
        self.notify_last_sequence_id = 0


class _FakeApp:
    def __init__(self, session: _FakeSession) -> None:
        self.session: Any = session
        self.session_sync_event = asyncio.Event()


def _response(*sequence_ids: int) -> SessionMessageResponse:
    return SessionMessageResponse(
        session_messages=[SessionMessage(sequence_id=s) for s in sequence_ids]
    )


async def test_sync_advances_notify_watermark_only() -> None:
    """同步只推进未读水位，不推进已读水位（last_sequence_id）。"""
    app = _FakeApp(_FakeSession())
    with patch.object(
        session_watch,
        "fetch_session_messages",
        new=AsyncMock(return_value=_response(1, 3)),
    ):
        await session_watch.sync_session_messages(cast(Any, app))
    assert app.session.notify_last_sequence_id == 3
    assert app.session.last_sequence_id == 0


async def test_sync_uses_current_watermark_as_cursor() -> None:
    """游标取自当前未读水位，重复调用只拉增量（幂等）。"""
    app = _FakeApp(_FakeSession())
    app.session.notify_last_sequence_id = 7
    fetch = AsyncMock(return_value=_response(8, 9))
    with patch.object(session_watch, "fetch_session_messages", new=fetch):
        await session_watch.sync_session_messages(cast(Any, app))
        await session_watch.sync_session_messages(cast(Any, app))
    assert app.session.notify_last_sequence_id == 9
    assert fetch.await_args_list[0].args == ("u", "g", 7)
    assert fetch.await_args_list[1].args == ("u", "g", 9)


async def test_sync_swallows_fetch_error() -> None:
    """拉取失败只记日志，不改动水位，也不抛出。"""
    app = _FakeApp(_FakeSession())
    app.session.notify_last_sequence_id = 4
    with patch.object(
        session_watch,
        "fetch_session_messages",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ):
        await session_watch.sync_session_messages(cast(Any, app))
    assert app.session.notify_last_sequence_id == 4


async def test_watch_establishes_baseline_and_stops_when_inactive() -> None:
    """进入界面先记基线；界面卸载（is_active 变 False）后循环自行退出。"""
    app = _FakeApp(_FakeSession())
    app.session.last_sequence_id = 5
    cursors: List[int] = []

    async def fake_fetch(user: str, game: str, since: int) -> SessionMessageResponse:
        cursors.append(since)
        return _response()

    def on_update() -> None:
        raise AssertionError("界面已卸载，不应再刷新徽标")

    with patch.object(
        session_watch, "fetch_session_messages", new=AsyncMock(side_effect=fake_fetch)
    ):
        await session_watch.watch_session_messages(
            cast(Any, app),
            on_update,
            is_active=lambda: len(cursors) == 0,
            interval=0.01,
        )

    assert app.session.notify_last_sequence_id == 5
    assert cursors == [5]


async def test_watch_returns_immediately_without_session() -> None:
    """未登录（session 为 None）时直接返回。"""
    app = _FakeApp(_FakeSession())
    app.session = None
    with patch.object(
        session_watch, "fetch_session_messages", new=AsyncMock()
    ) as fetch:
        await session_watch.watch_session_messages(cast(Any, app), lambda: None)
    fetch.assert_not_awaited()


def test_task_succeeded_listener_registration_is_idempotent() -> None:
    """同一监听器重复注册只保留一份；移除后不再触发。"""
    hits: List[int] = []

    def listener() -> None:
        hits.append(1)

    add_task_succeeded_listener(listener)
    add_task_succeeded_listener(listener)
    try:
        _notify_task_succeeded()
    finally:
        remove_task_succeeded_listener(listener)

    assert hits == [1]

    _notify_task_succeeded()
    assert hits == [1]
