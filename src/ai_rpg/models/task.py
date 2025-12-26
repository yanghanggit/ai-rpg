"""后台任务相关模型

本模块定义后台任务的状态和记录数据结构。
"""

from enum import StrEnum, unique
from typing import Optional, final
from pydantic import BaseModel


@final
@unique
class TaskStatus(StrEnum):
    """任务状态枚举

    定义后台任务的所有可能状态
    """

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@final
class TaskRecord(BaseModel):
    """任务记录模型

    记录后台任务的完整信息，包括状态、时间和错误信息
    """

    task_id: str
    status: TaskStatus
    start_time: str
    end_time: Optional[str] = None
    error: Optional[str] = None
