"""任务相关模型。

命名约定（全项目统一）：

- ``Task``：应用层的“任务”概念（进入队列、可追踪状态的工作单元）；
- ``job_id``：该任务在 Procrastinate 中的执行实例标识，是本项目**唯一**的任务标识字段
  （全仓不存在 ``task_id``）。

因此模块 / 模型 / 接口用 ``task`` 命名，而标识符参数与字段一律用 ``job_id``：
二者是「概念 : 标识符」的关系，不是同一层的两种叫法。
"""

from typing import Optional, final

from procrastinate.jobs import Status as ProcrastinateJobStatus
from pydantic import BaseModel


@final
class TaskSnapshot(BaseModel):
    """任务快照：由 Procrastinate 的 job 状态实时推导，失败错误取自 task_errors，本身不被持久化。

    ``job_id`` 为该任务在 Procrastinate 的执行实例标识；命名边界见模块 docstring。
    """

    job_id: int
    status: ProcrastinateJobStatus
    error: Optional[str] = None
