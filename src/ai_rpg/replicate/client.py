import asyncio
from typing import Final, List, Optional, final
import httpx
import traceback
from loguru import logger
from .protocol import (
    ImageGenerationRequest,
    ImageGenerationResponse,
)
import time
from ..configuration.server import ServerConfiguration
from dataclasses import dataclass


################################################################################################################################################################################
@dataclass
class ImageServiceUrlConfig:
    """ """

    base_url: str
    generate_url: str


################################################################################################################################################################################
@final
class ImageClient:

    # Static AsyncClient instance for all ChatClient instances
    _async_client: httpx.AsyncClient = httpx.AsyncClient()

    # Static URL configuration
    _image_service_url_config: Optional[ImageServiceUrlConfig] = None

    @classmethod
    def initialize_url_config(cls, server_settings: ServerConfiguration) -> None:

        cls._image_service_url_config = ImageServiceUrlConfig(
            base_url=f"http://localhost:{server_settings.image_generation_server_port}/",
            generate_url=f"http://localhost:{server_settings.image_generation_server_port}/api/generate/v1/",
        )

        logger.info(
            f"ImageClient initialized with Image Service URLs: {cls._image_service_url_config}"
        )

    ################################################################################################################################################################################
    @classmethod
    def get_async_client(cls) -> httpx.AsyncClient:
        return cls._async_client

    ################################################################################################################################################################################
    @classmethod
    async def close_async_client(cls) -> None:
        if cls._async_client is not None:
            await cls._async_client.aclose()
            cls._async_client = httpx.AsyncClient()

    ################################################################################################################################################################################
    def __init__(
        self,
        name: str,
        prompt: str,
        url: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> None:

        self._name = name
        assert self._name != "", "agent_name should not be empty"

        self._prompt: Final[str] = prompt
        assert self._prompt != "", "prompt should not be empty"

        self._response: ImageGenerationResponse = ImageGenerationResponse(
            images=[], elapsed_time=0.0
        )

        assert (
            self._image_service_url_config is not None
        ), "DeepSeek URL config is not initialized"

        self._url: Optional[str] = (
            url if url is not None else self._image_service_url_config.generate_url
        )

        self._timeout: Final[int] = timeout if timeout is not None else 30
        assert self._timeout > 0, "timeout should be positive"

    ################################################################################################################################################################################
    @property
    def name(self) -> str:
        """获取客户端名称"""
        return self._name

    ################################################################################################################################################################################
    @property
    def prompt(self) -> str:
        """获取发送给AI的提示词"""
        return self._prompt

    ################################################################################################################################################################################
    @property
    def url(self) -> str:
        """获取请求端点URL"""
        if self._url is None:
            return ""
        return self._url

    ################################################################################################################################################################################
    async def a_request_post(self) -> None:
        """ """

        try:

            logger.debug(f"{self._name} a_request prompt:\n{self._prompt}")

            start_time = time.time()

            response = await ImageClient.get_async_client().post(
                url=self.url,
                json=ImageGenerationRequest(configs=[]).model_dump(),
                timeout=self._timeout,
            )

            end_time = time.time()
            logger.debug(
                f"{self._name} a_request time:{end_time - start_time:.2f} seconds"
            )

            if response.status_code == 200:
                self._response = ImageGenerationResponse.model_validate(response.json())

            else:
                logger.error(
                    f"a_request-response Error: {response.status_code}, {response.text}"
                )

        except httpx.TimeoutException as e:
            logger.error(f"{self._name}: async timeout error: {type(e).__name__}: {e}")
        except httpx.ConnectError as e:
            logger.error(
                f"{self._name}: async connection error: {type(e).__name__}: {e}"
            )
        except httpx.RequestError as e:
            logger.error(f"{self._name}: async request error: {type(e).__name__}: {e}")
        except Exception as e:
            logger.error(
                f"{self._name}: unexpected async error: {type(e).__name__}: {e}"
            )
            logger.debug(f"{self._name}: full traceback:\n{traceback.format_exc()}")

    ################################################################################################################################################################################

    @staticmethod
    async def gather_request_post(clients: List["ImageClient"]) -> None:
        """ """
        if not clients:
            return

        coros = []
        for client in clients:
            coros.append(client.a_request_post())

        # 允许异常捕获，不中断其他请求
        start_time = time.time()
        batch_results = await asyncio.gather(*coros, return_exceptions=True)
        end_time = time.time()
        logger.debug(
            f"ChatClient.gather_request_post: {len(clients)} clients, {end_time - start_time:.2f} seconds"
        )

        # 记录失败请求
        failed_count = 0
        for i, result in enumerate(batch_results):
            if isinstance(result, Exception):
                client_name = clients[i].name if i < len(clients) else "unknown"
                logger.error(
                    f"Request failed for client '{client_name}': {type(result).__name__}: {result}"
                )
                failed_count += 1

        if failed_count > 0:
            logger.warning(
                f"ChatClient.gather_request_post: {failed_count}/{len(clients)} requests failed"
            )
        else:
            logger.debug(
                f"ChatClient.gather_request_post: All {len(clients)} requests completed successfully"
            )

    ################################################################################################################################################################################

    @staticmethod
    async def health_check() -> None:
        """ """
        if ImageClient._image_service_url_config is None:
            logger.warning("ImageClient URL configurations are not initialized")
            return

        base_urls = [
            ImageClient._image_service_url_config.base_url,
        ]

        for base_url in base_urls:
            try:
                response = await ImageClient.get_async_client().get(f"{base_url}")
                response.raise_for_status()
                # 打印response
                logger.debug(f"Health check response from {base_url}: {response.text}")
                logger.debug(f"Health check passed: {base_url}")
            except Exception as e:
                logger.error(f"Health check failed: {base_url}, error: {e}")

    ################################################################################################################################################################################
