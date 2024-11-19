from langserve import RemoteRunnable  # type: ignore
from loguru import logger
from typing import Optional, final


@final
class RemoteRunnableConnector:

    def __init__(self, url: str) -> None:
        self._url: str = url
        self._remote_runnable: Optional[RemoteRunnable] = None

    #################################################################################################################################################
    @property
    def url(self) -> str:
        return self._url

    #################################################################################################################################################
    async def establish_connection(self, message: str) -> bool:

        if self._remote_runnable is not None:
            logger.error(f"initialize_connection: already initialized = {self._url}")
            return False

        remote_runnable = await self._establish_remote_runnable(self._url, message)
        if remote_runnable is None:
            logger.error(
                f"initialize_connection: remote_runnable is None = {self._url}"
            )
            return False

        self._remote_runnable = remote_runnable
        return True

    #################################################################################################################################################
    async def _establish_remote_runnable(
        self, url: str, ping_message: str
    ) -> Optional[RemoteRunnable]:

        try:
            remote_runnable = RemoteRunnable(url)
            response = await remote_runnable.ainvoke(
                {
                    "input": ping_message,
                    "chat_history": [],
                }
            )

            if response is None:
                logger.error(f"initialize_connection: response is None")
                return None

            logger.info(f"initialize_connection: {response["output"]}")
            return remote_runnable

        except Exception as e:
            logger.error(f"initialize_connection error: {e}")

        return None

    #################################################################################################################################################
