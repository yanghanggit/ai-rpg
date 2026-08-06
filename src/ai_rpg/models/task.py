"""后台任务相关模型"""

from enum import StrEnum, unique
from typing import Optional, final
from pydantic import BaseModel


@final
@unique
class TaskStatus(StrEnum):
    """任务状态枚举"""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@final
class TaskRecord(BaseModel):
    """任务记录模型"""

    task_id: str
    status: TaskStatus
    start_time: str
    end_time: Optional[str] = None
    error: Optional[str] = None
