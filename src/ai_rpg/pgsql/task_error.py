"""任务失败错误持久化模型"""

from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base


class TaskErrorDB(Base):
    """记录任务（Procrastinate job）失败时的错误信息，仅在失败时写入一行"""

    __tablename__ = "task_errors"

    # 主键即 Procrastinate job id
    job_id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # 失败时捕获的异常信息
    error: Mapped[str] = mapped_column(Text, nullable=False)
