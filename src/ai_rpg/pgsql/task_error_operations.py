from typing import Optional
from .client import SessionLocal
from .task_error import TaskErrorDB


############################################################################################################
def save_task_error(job_id: str, error: str) -> TaskErrorDB:
    """保存后台任务失败时的错误信息"""

    # 创建一个新的数据库会话
    db = SessionLocal()

    try:
        task_error = TaskErrorDB(job_id=job_id, error=error)

        # 将记录添加到数据库会话并提交事务
        db.add(task_error)
        db.commit()
        db.refresh(task_error)

        # 返回保存的记录对象
        return task_error
    except Exception as e:
        db.rollback()
        raise e  # 重新抛出异常以便调用者处理
    finally:
        db.close()  # 确保数据库会话在操作完成后关闭


############################################################################################################
def get_task_error(job_id: str) -> Optional[str]:
    """获取指定任务的失败错误信息，不存在则返回 None"""

    # 创建一个新的数据库会话
    db = SessionLocal()
    try:
        record = db.query(TaskErrorDB).filter_by(job_id=job_id).first()
        return record.error if record is not None else None
    finally:
        db.close()  # 确保数据库会话在操作完成后关闭
