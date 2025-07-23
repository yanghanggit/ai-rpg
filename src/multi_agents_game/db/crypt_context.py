from passlib.context import CryptContext

# # 密码加密工具
crypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# 验证密码方法
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return crypt_context.verify(plain_password, hashed_password)
