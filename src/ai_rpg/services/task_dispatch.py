"""房间后台任务的统一派发入口。

所有针对某个玩家房间的后台任务都经 ``defer_room_task`` 派发：按
``room:{user_name}:{task.name}`` 加 ``queueing_lock``，同一房间同类任务已在排队时
拒绝重复入队，避免“锁内校验 → 出锁派发”的 TOCTOU 造成重复执行。
"""

from typing import Any

from procrastinate.exceptions import AlreadyEnqueued


###############################################################################################################################################
class RoomBusyError(Exception):
    """该房间已有同类任务在排队。"""

    def __init__(self, user_name: str) -> None:
        super().__init__(f"room busy: {user_name}")
        self.user_name: str = user_name


###############################################################################################################################################
async def defer_room_task(task: Any, *, user_name: str, **task_kwargs: Any) -> int:
    """派发房间任务，返回 job id；重复入队时抛 ``RoomBusyError``。"""
    queueing_lock = f"room:{user_name}:{task.name}"
    try:
        job_id: int = await task.configure(queueing_lock=queueing_lock).defer_async(
            user_name=user_name, **task_kwargs
        )
    except AlreadyEnqueued as exc:
        raise RoomBusyError(user_name) from exc
    return job_id


###############################################################################################################################################
