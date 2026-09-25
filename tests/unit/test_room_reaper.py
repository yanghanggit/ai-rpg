"""房间 TTL / 回收测试。"""

import asyncio
import time
from typing import cast

from ai_rpg.game.dbg_game import DBGGame
from ai_rpg.game.game_server import GameServer


class _FakeGame:
    def __init__(self) -> None:
        self.exited = False

    def exit(self) -> None:
        self.exited = True


async def test_reap_expired_removes_idle_room() -> None:
    server = GameServer()
    room = await server.create_room("alice")
    game = _FakeGame()
    room._dbg_game = cast(DBGGame, game)
    room._last_active_at = 0.0

    reaped = await server.reap_expired(ttl=10, now=time.monotonic())

    assert reaped == ["alice"]
    assert not server.has_room("alice")
    assert room.is_closed
    assert game.exited


async def test_reap_expired_keeps_active_room() -> None:
    server = GameServer()
    room = await server.create_room("alice")
    room._last_active_at = time.monotonic()

    reaped = await server.reap_expired(ttl=10)

    assert reaped == []
    assert server.has_room("alice")
    assert not room.is_closed


async def test_reap_expired_skips_busy_room() -> None:
    server = GameServer()
    room = await server.create_room("alice")
    started = asyncio.Event()
    release = asyncio.Event()

    async def hold() -> None:
        async with room.transaction():
            room._last_active_at = 0.0  # 标记为过期，但它仍处于忙状态
            started.set()
            await release.wait()

    task = asyncio.create_task(hold())
    await started.wait()

    reaped = await server.reap_expired(ttl=10, now=time.monotonic())

    assert reaped == []
    assert server.has_room("alice")

    release.set()
    await task


async def test_get_room_touches_activity() -> None:
    server = GameServer()
    room = await server.create_room("alice")
    room._last_active_at = 0.0

    server.get_room("alice")

    assert room._last_active_at > 0.0
