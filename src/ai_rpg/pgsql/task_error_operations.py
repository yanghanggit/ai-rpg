from typing import Optional
from .client import SessionLocal
from .task_error import TaskErrorDB


############################################################################################################
def save_task_error(job_id: int, error: str) -> None:
    """保存任务失败时的错误信息；同一 job 重复失败时覆盖旧记录"""

    # 创建一个新的数据库会话
    db = SessionLocal()

    try:
        # merge：job_id 已存在则更新，不存在则插入，避免主键冲突顶掉原始异常
        db.merge(TaskErrorDB(job_id=job_id, error=error))
        db.commit()
    except Exception as e:
        db.rollback()
        raise e  # 重新抛出异常以便调用者处理
    finally:
        db.close()  # 确保数据库会话在操作完成后关闭


############################################################################################################
def get_task_error(job_id: int) -> Optional[str]:
    """获取指定任务的失败错误信息，不存在则返回 None"""

    # 创建一个新的数据库会话
    db = SessionLocal()
    try:
        record = db.query(TaskErrorDB).filter_by(job_id=job_id).first()
        return record.error if record is not None else None
    finally:
        db.close()  # 确保数据库会话在操作完成后关闭
