from pydantic import BaseModel
from models.event_models import BaseEvent


# 玩家客户端消息，目前是测试。
class PlayerNotification(BaseModel):
    header: str = ""
    data: BaseEvent  # 要根部的类，其实只需要它的序列化能力，其余的不要，所以不要出现具体类型的调用！
