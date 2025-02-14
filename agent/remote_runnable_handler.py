from langserve import RemoteRunnable
from loguru import logger
from typing import Final, Optional, final, Any


@final
class RemoteRunnableHandler:

    def __init__(self, url: str) -> None:
        self._url: Final[str] = url
        logger.debug(f"{self._url}")
        self._remote_runnable: Optional[RemoteRunnable[Any, Any]] = None

    #################################################################################################################################################
    @property
    def url(self) -> str:
        return self._url

    #################################################################################################################################################
    async def establish_connection(self, ping_message: str) -> bool:

        if self._remote_runnable is not None:
            logger.error(f"pin establish_connection: already initialized = {self._url}")
            return False

        remote_runnable = await self._establish_remote_runnable(self._url, ping_message)
        if remote_runnable is None:
            logger.error(
                f"pin establish_connection: remote_runnable is None = {self._url}"
            )
            return False

        self._remote_runnable = remote_runnable
        return True

    #################################################################################################################################################
    async def _establish_remote_runnable(
        self, url: str, ping_message: str
    ) -> Optional[RemoteRunnable[Any, Any]]:

        try:

            # server_url = "http://localhost:8100/v1/llm_serve/chat/"
            remote_runnable: RemoteRunnable[Any, Any] = RemoteRunnable(url)
            response = await remote_runnable.ainvoke(
                {
                    "agent_name": "",
                    "user_name": "",
                    "input": ping_message,
                    "chat_history": [],
                }
            )

            if response is None:
                logger.error(f"_establish_remote_runnable: response is None")
                return None

            logger.info(f"_establish_remote_runnable: {response["output"]}")
            return remote_runnable

        except Exception as e:
            logger.error(f"_establish_remote_runnable error: {e}")

        return None

    #################################################################################################################################################
