"""后台任务失败错误持久化模型"""

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base


class TaskErrorDB(Base):
    """记录后台任务（Procrastinate job）失败时的错误信息，仅在失败时写入一行"""

    __tablename__ = "task_errors"

    # 主键为 Procrastinate job id 的字符串形式
    job_id: Mapped[str] = mapped_column(Text, primary_key=True)

    # 失败时捕获的异常信息
    error: Mapped[str] = mapped_column(Text, nullable=False)
