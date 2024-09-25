from langserve import RemoteRunnable  # type: ignore
from loguru import logger
from typing import Optional


class RemoteRunnableWrapper:

    def __init__(self, url: str) -> None:
        self._url: str = url
        self._remote_runnable: Optional[RemoteRunnable] = None

    def _initialize_connection(self) -> None:

        if self._remote_runnable is not None:
            return

        try:
            self._remote_runnable = RemoteRunnable(self._url)
        except Exception as e:
            logger.error(f"initialize_connection error: {e}")
