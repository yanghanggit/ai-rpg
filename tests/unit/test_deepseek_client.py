"""Unit tests for DeepSeekClient.chat() and DeepSeekClient.batch_chat()."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from src.ai_rpg.deepseek.client import DeepSeekClient
from src.ai_rpg.models.messages import SystemMessage


# ---------------------------------------------------------------------------
# 公共 fixtures
# ---------------------------------------------------------------------------

_SYSTEM = SystemMessage(content="你是一个测试助手。")


def _make_client(name: str = "test") -> DeepSeekClient:
    return DeepSeekClient(
        name=name,
        prompt="测试提示词",
        context=[_SYSTEM],
    )


def _make_200_response(content: str = "ok") -> MagicMock:
    """构造一个模拟 HTTP 200 响应，携带最小合法的 DeepSeek JSON 结构。"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"content": content, "role": "assistant"},
            }
        ],
        "usage": {
            "prompt_cache_hit_tokens": 10,
            "prompt_cache_miss_tokens": 90,
        },
    }
    return mock_response


def _make_error_response(status_code: int) -> MagicMock:
    """构造一个模拟非 200 HTTP 响应。"""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.text = f"error {status_code}"
    mock_response.request = MagicMock()
    return mock_response


# ---------------------------------------------------------------------------
# chat() 正常路径
# ---------------------------------------------------------------------------


class TestChatSuccess:
    @pytest.mark.asyncio
    async def test_chat_parses_response_on_200(self) -> None:
        """HTTP 200 时 response_content 应被正确填充。"""
        client = _make_client()
        mock_response = _make_200_response("hello")

        with patch.object(
            DeepSeekClient.get_async_client(),
            "post",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            await client.chat()

        assert client.response_content == "hello"
        assert client.finish_reason == "stop"
        assert client.response_ai_message is not None

    @pytest.mark.asyncio
    async def test_chat_records_cache_tokens(self) -> None:
        """HTTP 200 时 token 计数应正确写入。"""
        client = _make_client()
        mock_response = _make_200_response()

        with patch.object(
            DeepSeekClient.get_async_client(),
            "post",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            await client.chat()

        assert client.prompt_cache_hit_tokens == 10
        assert client.prompt_cache_miss_tokens == 90


# ---------------------------------------------------------------------------
# chat() 异常传播路径
# ---------------------------------------------------------------------------


class TestChatRaisesOnNetworkErrors:
    @pytest.mark.asyncio
    async def test_chat_raises_on_timeout(self) -> None:
        """超时时 chat() 应向上 raise httpx.TimeoutException。"""
        client = _make_client()

        with patch.object(
            DeepSeekClient.get_async_client(),
            "post",
            new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("timed out"),
        ):
            with pytest.raises(httpx.TimeoutException):
                await client.chat()

    @pytest.mark.asyncio
    async def test_chat_raises_on_connect_error(self) -> None:
        """连接失败时 chat() 应向上 raise httpx.ConnectError。"""
        client = _make_client()

        with patch.object(
            DeepSeekClient.get_async_client(),
            "post",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("connection refused"),
        ):
            with pytest.raises(httpx.ConnectError):
                await client.chat()

    @pytest.mark.asyncio
    async def test_chat_raises_on_request_error(self) -> None:
        """通用请求错误时 chat() 应向上 raise httpx.RequestError。"""
        client = _make_client()

        with patch.object(
            DeepSeekClient.get_async_client(),
            "post",
            new_callable=AsyncMock,
            side_effect=httpx.RequestError("bad request"),
        ):
            with pytest.raises(httpx.RequestError):
                await client.chat()

    @pytest.mark.asyncio
    async def test_chat_raises_http_status_error_on_non_200(self) -> None:
        """HTTP 非 200 时 chat() 应 raise httpx.HTTPStatusError。"""
        client = _make_client()
        mock_response = _make_error_response(429)

        with patch.object(
            DeepSeekClient.get_async_client(),
            "post",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            with pytest.raises(httpx.HTTPStatusError):
                await client.chat()

    @pytest.mark.asyncio
    async def test_chat_response_ai_message_none_after_error(self) -> None:
        """异常后 response_ai_message 应保持 None（未写入脏数据）。"""
        client = _make_client()

        with patch.object(
            DeepSeekClient.get_async_client(),
            "post",
            new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("timed out"),
        ):
            with pytest.raises(httpx.TimeoutException):
                await client.chat()

        assert client.response_ai_message is None


# ---------------------------------------------------------------------------
# batch_chat() 使用 results 计数
# ---------------------------------------------------------------------------


class TestBatchChat:
    @pytest.mark.asyncio
    async def test_batch_chat_all_succeed(self) -> None:
        """全部成功时不记录 warning，response_content 均有内容。"""
        clients = [_make_client(f"c{i}") for i in range(3)]
        mock_response = _make_200_response("reply")

        with patch.object(
            DeepSeekClient.get_async_client(),
            "post",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            await DeepSeekClient.batch_chat(clients)

        for c in clients:
            assert c.response_ai_message is not None

    @pytest.mark.asyncio
    async def test_batch_chat_counts_failures_via_results(self) -> None:
        """部分失败时 batch_chat 应通过 results 记录失败数，而不依赖 succeeded。"""
        clients = [_make_client(f"c{i}") for i in range(3)]

        # c0 超时，c1/c2 成功
        responses = [
            httpx.TimeoutException("timed out"),
            _make_200_response("ok"),
            _make_200_response("ok"),
        ]
        call_count = 0

        async def side_effect(*args, **kwargs):  # type: ignore[no-untyped-def]
            nonlocal call_count
            r = responses[call_count]
            call_count += 1
            if isinstance(r, Exception):
                raise r
            return r

        with patch.object(
            DeepSeekClient.get_async_client(),
            "post",
            new_callable=AsyncMock,
            side_effect=side_effect,
        ):
            with patch("src.ai_rpg.deepseek.client.logger") as mock_logger:
                await DeepSeekClient.batch_chat(clients)

        # 应触发 warning（1/3 failed）
        mock_logger.warning.assert_called_once()
        warning_msg: str = mock_logger.warning.call_args[0][0]
        assert "1/3" in warning_msg

    @pytest.mark.asyncio
    async def test_batch_chat_all_fail(self) -> None:
        """全部失败时 warning 应包含正确的失败比例。"""
        clients = [_make_client(f"c{i}") for i in range(2)]

        with patch.object(
            DeepSeekClient.get_async_client(),
            "post",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("refused"),
        ):
            with patch("src.ai_rpg.deepseek.client.logger") as mock_logger:
                await DeepSeekClient.batch_chat(clients)

        mock_logger.warning.assert_called_once()
        warning_msg = mock_logger.warning.call_args[0][0]
        assert "2/2" in warning_msg

    @pytest.mark.asyncio
    async def test_batch_chat_empty_clients(self) -> None:
        """空列表时 batch_chat 应直接返回，不抛出异常。"""
        await DeepSeekClient.batch_chat([])  # 不应抛出

    @pytest.mark.asyncio
    async def test_batch_chat_http_status_error_counted_as_failure(self) -> None:
        """HTTP 非 200（HTTPStatusError）也应被计入失败。"""
        clients = [_make_client("c0")]
        mock_response = _make_error_response(500)

        with patch.object(
            DeepSeekClient.get_async_client(),
            "post",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            with patch("src.ai_rpg.deepseek.client.logger") as mock_logger:
                await DeepSeekClient.batch_chat(clients)

        mock_logger.warning.assert_called_once()
        warning_msg = mock_logger.warning.call_args[0][0]
        assert "1/1" in warning_msg
