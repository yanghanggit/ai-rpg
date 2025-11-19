from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column
from .base import UUIDBase


# 用户模型
class UserDB(UUIDBase):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(
        String(100), index=True, nullable=True
    )
    # 新增创建时间字段
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # 新增更新时间字段
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
