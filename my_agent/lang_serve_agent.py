from langserve import RemoteRunnable  # type: ignore
from loguru import logger
from typing import List, Union, Optional
from langchain_core.messages import HumanMessage, AIMessage


class LangServeAgent:

    def __init__(self, name: str, url: str) -> None:
        self._name: str = name
        self._url: str = url
        self._remote_runnable: Optional[RemoteRunnable] = None
        self._chat_history: List[Union[HumanMessage, AIMessage]] = []

    ################################################################################################################################################################################
    def connect(self) -> bool:

        if self._remote_runnable is not None:
            logger.error(f"connect: {self._name} already connected.")
            return False

        if self._url == "":
            logger.error(
                f"connect: {self._name} have no url. 请确认是默认玩家，否则检查game_settings.json中配置。"
            )
            return False

        try:
            self._remote_runnable = RemoteRunnable(self._url)
            assert self._remote_runnable is not None
            self._chat_history = []
            return True
        except Exception as e:
            logger.error(e)

        return False


################################################################################################################################################################################
