from langserve import RemoteRunnable  # type: ignore
from loguru import logger
from typing import List, Union, Optional
from langchain_core.messages import HumanMessage, AIMessage


class RemoteRunnableWrapper:

    def __init__(self, url: str) -> None:
        logger.info(f"LangServeRemoteRunnable: {url}")
        self._url: str = url
        self._remote_runnable: Optional[RemoteRunnable] = None

    def connect(self) -> None:

        if self._remote_runnable is not None:
            logger.warning(f"connect: {self._url} already connected.")
            return

        if self._url == "":
            logger.error(
                f"connect: {self._url} have no url. 请确认是默认玩家，否则检查game_settings.json中配置。"
            )
            return

        try:
            self._remote_runnable = RemoteRunnable(self._url)
        except Exception as e:
            logger.error(e)


class LangServeAgent:

    def __init__(
        self, name: str, remote_runnable_wrapper: RemoteRunnableWrapper
    ) -> None:
        self._name: str = name
        self._remote_runnable_wrapper = remote_runnable_wrapper
        self._chat_history: List[Union[HumanMessage, AIMessage]] = []

    def connect(self) -> None:
        self._remote_runnable_wrapper.connect()
