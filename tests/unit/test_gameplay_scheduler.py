"""游戏玩法定时器（骨架）测试。"""

import asyncio
from typing import List

import pytest

from ai_rpg.game.game_server import GameServer
from ai_rpg.game.player_room import PlayerRoom
from ai_rpg.services import gameplay_scheduler


async def test_tick_calls_hook_under_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    server = GameServer()
    await server.create_room("alice")
    seen: List[str] = []
    lock_held: List[bool] = []

    async def hook(room: PlayerRoom) -> None:
        lock_held.append(room.is_busy)  # 回调应在房间锁内执行
        seen.append(room.username)

    monkeypatch.setattr(gameplay_scheduler, "on_room_tick", hook)

    await gameplay_scheduler._tick_once(server)

    assert seen == ["alice"]
    assert lock_held == [True]


async def test_tick_skips_busy_room(monkeypatch: pytest.MonkeyPatch) -> None:
    server = GameServer()
    room = await server.create_room("alice")
    seen: List[str] = []
    started = asyncio.Event()
    release = asyncio.Event()

    async def hold() -> None:
        async with room.transaction():
            started.set()
            await release.wait()

    task = asyncio.create_task(hold())
    await started.wait()

    async def hook(r: PlayerRoom) -> None:
        seen.append(r.username)

    monkeypatch.setattr(gameplay_scheduler, "on_room_tick", hook)

    await gameplay_scheduler._tick_once(server)

    assert seen == []

    release.set()
    await task


async def test_tick_skips_closed_room(monkeypatch: pytest.MonkeyPatch) -> None:
    server = GameServer()
    room = await server.create_room("alice")
    await room.close()
    seen: List[str] = []

    async def hook(r: PlayerRoom) -> None:
        seen.append(r.username)

    monkeypatch.setattr(gameplay_scheduler, "on_room_tick", hook)

    await gameplay_scheduler._tick_once(server)

    assert seen == []
