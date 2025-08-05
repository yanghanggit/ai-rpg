import sys
import os
# 将 src 目录添加到模块搜索路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from multi_agents_game.chat_services.chat_server_fastapi import app
from multi_agents_game.config import (
    DEFAULT_SERVER_SETTINGS_CONFIG,
)


##################################################################################################################
def main() -> None:

    if DEFAULT_SERVER_SETTINGS_CONFIG.num_chat_service_instances != 1:
        raise ValueError(
            "This script is only for running a single instance of the chat server."
        )

    import uvicorn

    uvicorn.run(
        app,
        host="localhost",
        port=DEFAULT_SERVER_SETTINGS_CONFIG.chat_service_base_port,
    )


##################################################################################################################

if __name__ == "__main__":
    main()

##################################################################################################################
