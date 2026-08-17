from .client import SessionLocal
from .user import UserDB


############################################################################################################
def save_user(username: str, hashed_password: str, display_name: str) -> UserDB:
    """
    保存用户到PostgreSQL数据库
    """

    # 创建一个新的数据库会话
    db = SessionLocal()

    try:

        # 检查用户是否已存在
        user = UserDB(
            username=username,
            hashed_password=hashed_password,
            display_name=display_name,
            # created_at 和 updated_at 会自动处理
        )

        # 将用户添加到数据库会话并提交事务
        db.add(user)

        # 提交事务并刷新用户对象以获取数据库生成的ID
        db.commit()

        # 刷新用户对象以获取数据库生成的ID
        db.refresh(user)

        # 返回保存的用户对象
        return user
    except Exception as e:
        db.rollback()
        raise e  # 重新抛出异常以便调用者处理
    finally:
        db.close()  # 确保数据库会话在操作完成后关闭


############################################################################################################
def has_user(username: str) -> bool:
    """
    检查用户是否存在于PostgreSQL数据库中
    """

    # 创建一个新的数据库会话
    db = SessionLocal()
    try:

        # 使用参数化查询检查用户是否存在
        user_exists = db.query(UserDB).filter_by(username=username).first() is not None
        return user_exists

    finally:
        db.close()  # 确保数据库会话在操作完成后关闭


############################################################################################################
def get_user(username: str) -> UserDB:
    """
    从PostgreSQL数据库获取用户
    """

    # 创建一个新的数据库会话
    db = SessionLocal()
    try:

        # 使用参数化查询获取用户对象
        user = db.query(UserDB).filter_by(username=username).first()
        if not user:
            raise ValueError(f"用户 '{username}' 不存在")

        # 返回获取的用户对象
        return user

    finally:
        db.close()  # 确保数据库会话在操作完成后关闭


############################################################################################################
