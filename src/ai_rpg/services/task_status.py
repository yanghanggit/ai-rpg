"""后台任务状态查询模块

任务状态不由本模块持久化，而是每次查询时从 Procrastinate 的 job 状态实时推导；
仅失败时的错误文本被持久化在 `task_errors` 表中。
"""

from procrastinate.jobs import Status as ProcrastinateJobStatus
from ..models import BackgroundTaskStatus, TaskStatusView
from ..pgsql import get_task_error, procrastinate_app


###############################################################################################################################################
async def get_task_status_view(job_id: str) -> TaskStatusView:
    """查询指定任务的当前状态视图"""

    job_status = await procrastinate_app.job_manager.get_job_status_async(int(job_id))

    # 本项目从不调用 cancel/abort，CANCELLED/ABORTING/ABORTED 不会出现，统一按未完成处理
    if job_status == ProcrastinateJobStatus.SUCCEEDED:
        status = BackgroundTaskStatus.COMPLETED
    elif job_status == ProcrastinateJobStatus.FAILED:
        status = BackgroundTaskStatus.FAILED
    else:
        status = BackgroundTaskStatus.RUNNING

    error = get_task_error(job_id) if status == BackgroundTaskStatus.FAILED else None

    return TaskStatusView(job_id=job_id, status=status, error=error)
