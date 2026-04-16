from typing import Final, final
from pydantic import BaseModel


@final
class ServerConfiguration(BaseModel):
    game_server_port: int = 8000
    replicate_image_generation_server_port: int = 8200


# 给一个默认的！
server_configuration: Final[ServerConfiguration] = ServerConfiguration()
