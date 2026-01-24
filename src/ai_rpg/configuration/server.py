from typing import Final, final
from pydantic import BaseModel


@final
class ServerConfiguration(BaseModel):
    game_server_port: int = 8000
    deepseek_chat_server_port: int = 8100
    image_generation_server_port: int = 8200


# 给一个默认的！
server_configuration: Final[ServerConfiguration] = ServerConfiguration()
