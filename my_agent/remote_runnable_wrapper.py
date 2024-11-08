from langserve import RemoteRunnable  # type: ignore
from loguru import logger
from typing import Optional, final


@final
class RemoteRunnableWrapper:

    def __init__(self, url: str) -> None:
        self._url: str = url
        self._remote_runnable: Optional[RemoteRunnable] = None

    #################################################################################################################################################
    def initialize_connection(self) -> bool:

        if self._remote_runnable is not None:
            logger.error(f"initialize_connection: already initialized = {self._url}")
            return False

        remote_runnable = self._establish_remote_connection(self._url)
        if remote_runnable is None:
            logger.error(
                f"initialize_connection: remote_runnable is None = {self._url}"
            )
            return False

        self._remote_runnable = remote_runnable
        return True

    #################################################################################################################################################
    def _establish_remote_connection(self, url: str) -> Optional[RemoteRunnable]:

        try:
            remote_runnable = RemoteRunnable(url)
            response = remote_runnable.invoke(
                {
                    "input": "hello world!",
                    "chat_history": [],
                }
            )

            if response is None:
                logger.error(f"initialize_connection: response is None")
                return None

            return remote_runnable

        except Exception as e:
            logger.error(f"initialize_connection error: {e}")

        return None

    #################################################################################################################################################
