"""
密码加密与验证模块

本模块提供基于 bcrypt 算法的密码哈希和验证功能。
使用 passlib 库来处理密码的安全存储和验证，确保用户密码的安全性。

主要功能:
    - 密码哈希加密 (hash_password)
    - 密码验证 (verify_password)

使用的加密方案:
    - bcrypt: 业界标准的密码哈希算法，具有自适应性和高安全性
"""

from typing import Final
from passlib.context import CryptContext

# 密码加密上下文
# 使用 bcrypt 作为主要加密方案，deprecated="auto" 确保旧方案自动更新
pwd_context: Final[CryptContext] = CryptContext(schemes=["bcrypt"], deprecated="auto")


############################################################################################################
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证明文密码是否与哈希密码匹配。

    Args:
        plain_password: 用户输入的明文密码
        hashed_password: 存储在数据库中的哈希密码

    Returns:
        bool: 密码匹配返回 True，否则返回 False

    Example:
        >>> hashed = hash_password("my_password")
        >>> verify_password("my_password", hashed)
        True
        >>> verify_password("wrong_password", hashed)
        False
    """
    return bool(pwd_context.verify(plain_password, hashed_password))


############################################################################################################
def hash_password(plain_password: str) -> str:
    """
    对明文密码进行哈希加密。

    使用 bcrypt 算法将明文密码转换为安全的哈希值，
    该哈希值可以安全地存储在数据库中。

    Args:
        plain_password: 需要加密的明文密码

    Returns:
        str: 加密后的哈希密码字符串

    Example:
        >>> hashed = hash_password("my_secure_password")
        >>> print(hashed)
        '$2b$12$...'  # bcrypt 格式的哈希值
    """
    return pwd_context.hash(plain_password)
