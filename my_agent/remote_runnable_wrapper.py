from langserve import RemoteRunnable  # type: ignore
from loguru import logger
from typing import Optional, final


@final
class RemoteRunnableWrapper:

    def __init__(self, url: str) -> None:
        self._url: str = url
        self._remote_runnable: Optional[RemoteRunnable] = None

    def initialize_connection(self) -> bool:

        if self._remote_runnable is not None:
            logger.error(f"initialize_connection: already initialized = {self._url}")
            return False

        try:

            self._remote_runnable = RemoteRunnable(self._url)
            return True

        except Exception as e:

            logger.error(f"initialize_connection error: {e}")

        return False
