from uuid import UUID, uuid4

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# 基类定义
class Base(DeclarativeBase):
    pass


class UUIDBase(Base):
    """包含UUID主键的基类"""

    __abstract__ = True

    id: Mapped[UUID] = mapped_column(primary_key=True, index=True, default=uuid4)
