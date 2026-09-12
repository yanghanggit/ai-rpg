"""任务相关模型"""

from typing import Optional, final

from procrastinate.jobs import Status as ProcrastinateJobStatus
from pydantic import BaseModel


@final
class TaskStatusView(BaseModel):
    """任务状态视图：由 Procrastinate 的 job 状态实时推导，失败错误取自 task_errors，本身不被持久化"""

    job_id: int
    status: ProcrastinateJobStatus
    error: Optional[str] = None
