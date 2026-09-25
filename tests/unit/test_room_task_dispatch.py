"""房间任务派发助手测试。"""

from typing import Any, Optional

import pytest
from procrastinate.exceptions import AlreadyEnqueued

from ai_rpg.services.task_dispatch import RoomBusyError, defer_room_task


class _FakeTask:
    """模拟 Procrastinate Task 的 configure / defer_async 调用链。"""

    name = "fake.task"

    def __init__(self, exc: Optional[Exception] = None) -> None:
        self._exc = exc
        self.queueing_lock: Optional[str] = None
        self.deferred: Optional[dict[str, Any]] = None

    def configure(self, **options: Any) -> "_FakeTask":
        self.queueing_lock = options.get("queueing_lock")
        return self

    async def defer_async(self, **kwargs: Any) -> int:
        if self._exc is not None:
            raise self._exc
        self.deferred = kwargs
        return 123


async def test_defer_room_task_sets_lock_and_passes_kwargs() -> None:
    task = _FakeTask()

    job_id = await defer_room_task(task, user_name="alice", card_name="x")

    assert job_id == 123
    assert task.queueing_lock == "room:alice:fake.task"
    assert task.deferred == {"user_name": "alice", "card_name": "x"}


async def test_defer_room_task_duplicate_raises_room_busy() -> None:
    task = _FakeTask(exc=AlreadyEnqueued("already enqueued"))

    with pytest.raises(RoomBusyError) as excinfo:
        await defer_room_task(task, user_name="alice")

    assert excinfo.value.user_name == "alice"
