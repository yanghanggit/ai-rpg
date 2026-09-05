"""后台任务相关模型"""

from enum import StrEnum, unique
from typing import Optional, final
from pydantic import BaseModel


@final
@unique
class BackgroundTaskStatus(StrEnum):
    """后台任务状态枚举"""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@final
class TaskStatusView(BaseModel):
    """后台任务状态视图：每次查询时由 Procrastinate 的 job 状态 + 失败错误表现算得出，本身不被持久化"""

    job_id: str
    status: BackgroundTaskStatus
    error: Optional[str] = None
