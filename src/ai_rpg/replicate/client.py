"""Replicate 图片生成客户端模块

提供异步图片生成客户端，支持单张和批量生成。
核心功能：
- 异步请求 Replicate 图片生成服务
- 批量并发生成多张图片
- 连接池管理和健康检查
"""

import asyncio
from typing import Final, List, Optional, final
import httpx
import traceback
from loguru import logger
from .protocol import (
    ImageGenerationRequest,
    ImageGenerationResponse,
    ImageGenerationConfig,
)
import time
from ..configuration.server import ServerConfiguration
from dataclasses import dataclass


################################################################################################################################################################################
@dataclass
class ImageServiceUrlConfig:
    """图片服务 URL 配置

    Attributes:
        base_url: 服务基础 URL
        generate_url: 图片生成 API 端点
    """

    base_url: str
    generate_url: str


################################################################################################################################################################################
@final
class ImageClient:
    """Replicate 图片生成客户端

    封装对 Replicate 图片生成服务的异步调用。
    使用类级别的连接池和 URL 配置实现资源共享。
    """

    # 所有实例共享的异步 HTTP 客户端（连接池）
    _async_client: httpx.AsyncClient = httpx.AsyncClient()

    # 类级别的 URL 配置
    _image_service_url_config: Optional[ImageServiceUrlConfig] = None

    @classmethod
    def initialize_url_config(cls, server_settings: ServerConfiguration) -> None:
        """初始化服务 URL 配置

        Args:
            server_settings: 服务器配置对象
        """
        cls._image_service_url_config = ImageServiceUrlConfig(
            base_url=f"http://localhost:{server_settings.image_generation_server_port}/",
            generate_url=f"http://localhost:{server_settings.image_generation_server_port}/api/generate/v1",
        )

        logger.info(
            f"ImageClient initialized with Image Service URLs: {cls._image_service_url_config}"
        )

    ################################################################################################################################################################################
    @classmethod
    def get_async_client(cls) -> httpx.AsyncClient:
        """获取共享的异步 HTTP 客户端"""
        return cls._async_client

    ################################################################################################################################################################################
    @classmethod
    async def close_async_client(cls) -> None:
        """关闭并重置异步 HTTP 客户端"""
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
        """初始化图片生成客户端

        Args:
            name: 客户端标识名称
            prompt: 图片生成提示词
            url: 自定义服务 URL，默认使用配置的 URL
            timeout: 请求超时时间（秒），默认 30 秒
        """
        self._name = name
        assert self._name != "", "client name should not be empty"

        self._prompt: Final[str] = prompt
        assert self._prompt != "", "prompt should not be empty"

        self._response: ImageGenerationResponse = ImageGenerationResponse(
            images=[], elapsed_time=0.0
        )

        assert (
            self._image_service_url_config is not None
        ), "Image service URL config is not initialized"

        self._url: Optional[str] = (
            url if url is not None else self._image_service_url_config.generate_url
        )

        self._timeout: Final[int] = timeout if timeout is not None else 60
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
    async def generate(self) -> None:
        """异步生成图片

        发送图片生成请求到 Replicate 服务，结果保存在 _response 属性中。
        自动处理网络异常和超时。
        """

        try:

            logger.debug(f"{self._name} a_request prompt:\n{self._prompt}")

            start_time = time.time()

            # 构建请求配置
            config = ImageGenerationConfig(
                prompt=self._prompt,
                model="nano-banana",
                aspect_ratio=None,
                seed=None,
            )

            # 构建完整请求
            request_payload = ImageGenerationRequest(configs=[config])

            # 发送请求
            response = await ImageClient.get_async_client().post(
                url=self.url,
                json=request_payload.model_dump(),
                timeout=self._timeout,
            )

            end_time = time.time()
            logger.debug(
                f"{self._name} a_request time:{end_time - start_time:.2f} seconds"
            )

            # 处理响应
            if response.status_code == 200:
                self._response = ImageGenerationResponse.model_validate(response.json())
                logger.info(
                    f"{self._name} successfully generated {len(self._response.images)} image(s)"
                )
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
    async def batch_generate(clients: List["ImageClient"]) -> None:
        """批量并发生成多张图片

        Args:
            clients: 图片客户端列表

        Note:
            使用 asyncio.gather 实现并发，单个请求失败不影响其他请求。
        """
        if not clients:
            return

        coros = []
        for client in clients:
            coros.append(client.generate())

        start_time = time.time()
        batch_results = await asyncio.gather(*coros, return_exceptions=True)
        end_time = time.time()
        logger.debug(
            f"ImageClient.batch_generate: {len(clients)} clients, {end_time - start_time:.2f} seconds"
        )

        # 统计失败请求
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
                f"ImageClient.batch_generate: {failed_count}/{len(clients)} requests failed"
            )
        else:
            logger.debug(
                f"ImageClient.batch_generate: All {len(clients)} requests completed successfully"
            )

    ################################################################################################################################################################################

    @staticmethod
    async def health_check() -> None:
        """健康检查

        检查图片生成服务的可用性，记录检查结果到日志。
        """
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
                logger.debug(f"Health check response from {base_url}: {response.text}")
                logger.debug(f"Health check passed: {base_url}")
            except Exception as e:
                logger.error(f"Health check failed: {base_url}, error: {e}")

    ################################################################################################################################################################################
