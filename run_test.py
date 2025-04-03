from typing import List

# from pydantic import BaseModel
from models.client_message_v_0_0_1 import (
    ClientMessage,
    MappingMessage,
    ClientMessageHead,
)
from models.api_v_0_0_1 import StartResponse
from loguru import logger


def _test_base_model() -> None:

    ## 测试消息
    test: List[ClientMessage] = [
        ClientMessage(
            head=ClientMessageHead.NONE,
            body="",
        ),
        ClientMessage(
            head=ClientMessageHead.AGENT_EVENT,
            body="",
        ),
        ClientMessage(
            head=ClientMessageHead.AGENT_EVENT,
            body=MappingMessage(
                data={"agent1": ["actor1", "actor2"], "agent2": ["hhhh"]}
            ).model_dump_json(),
        ),
    ]

    ret = StartResponse(
        client_messages=test,
        error=0,
        message=f"启动游戏成功！!=",
    )

    logger.debug(f"start/v1:game start, ret: \n{ret.model_dump_json()}")

    logger.info("Hello World!")


###########################################################################################################################

if __name__ == "__main__":
    _test_base_model()
