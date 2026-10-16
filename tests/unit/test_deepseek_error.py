"""DeepSeek 通讯层错误模型与单次通讯结果记录的单元测试。

覆盖：
- DeepSeekError 的 retryable 判定；
- DeepSeekClient.chat() 失败时记录 self.error 并抛出 DeepSeekError；
- chat() 每次调用开头重置响应态（供业务层重试时使用）；
- batch_chat() 返回与入参对齐的失败列表。
"""

import asyncio
from typing import Any, Dict, List, Optional, Union

import httpx
import pytest

from ai_rpg.deepseek import DeepSeekError
from ai_rpg.deepseek.batch import batch_chat
from ai_rpg.deepseek.client import DeepSeekClient


#######################################################################################################################################
# 测试替身
#######################################################################################################################################
class _FakeResponse:
    """模拟 httpx.Response 的最小面。"""

    def __init__(
        self, status_code: int, text: str = "", payload: Optional[Dict[str, Any]] = None
    ):
        self.status_code = status_code
        self.text = text
        self._payload = payload

    def json(self) -> Dict[str, Any]:
        assert self._payload is not None, "该响应不应被解析"
        return self._payload


class _FakeHTTPClient:
    """模拟 httpx.AsyncClient：post() 按预设行为抛出或返回。"""

    def __init__(self, outcome: Union[BaseException, _FakeResponse]):
        self._outcome = outcome

    async def post(self, **kwargs: Any) -> _FakeResponse:
        if isinstance(self._outcome, BaseException):
            raise self._outcome
        return self._outcome


def _success_payload(content: str = "hi") -> Dict[str, Any]:
    return {
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


def _make_client(name: str = "测试") -> DeepSeekClient:
    return DeepSeekClient(label=name, input_message="ping", messages=[])


#######################################################################################################################################
# DeepSeekError.retryable 判定
#######################################################################################################################################
class TestDeepSeekErrorRetryable:
    @pytest.mark.parametrize(
        "kind,status_code,expected",
        [
            ("timeout", None, True),
            ("connection", None, True),
            ("api", 429, True),
            ("api", 408, True),
            ("api", 500, True),
            ("api", 503, True),
            ("api", 400, False),
            ("api", 401, False),
            ("api", 402, False),
            ("api", 422, False),
            ("api", None, False),
        ],
    )
    def test_retryable_classification(
        self, kind: str, status_code: Optional[int], expected: bool
    ) -> None:
        err = DeepSeekError("角色.无名", "boom", kind=kind, status_code=status_code)  # type: ignore[arg-type]
        assert err.retryable is expected
        assert err.label == "角色.无名"
        assert err.status_code == status_code
        assert "[角色.无名]" in str(err)


#######################################################################################################################################
# 单次通讯：记录 + 抛出
#######################################################################################################################################
class TestChatErrorRecording:
    @pytest.mark.asyncio
    async def test_timeout_records_and_raises(self) -> None:
        client = _make_client()
        http = _FakeHTTPClient(httpx.TimeoutException("read timeout"))

        with pytest.raises(DeepSeekError) as excinfo:
            await client.chat(client=http)  # type: ignore[arg-type]

        assert excinfo.value.kind == "timeout"
        assert excinfo.value.retryable is True
        assert client.error is excinfo.value

    @pytest.mark.asyncio
    async def test_http_503_records_api_error(self) -> None:
        client = _make_client()
        http = _FakeHTTPClient(_FakeResponse(503, text="server busy"))

        with pytest.raises(DeepSeekError) as excinfo:
            await client.chat(client=http)  # type: ignore[arg-type]

        assert excinfo.value.kind == "api"
        assert excinfo.value.status_code == 503
        assert excinfo.value.retryable is True
        assert client.error is excinfo.value
        assert client.response_ai_message is None

    @pytest.mark.asyncio
    async def test_http_401_is_not_retryable(self) -> None:
        client = _make_client()
        http = _FakeHTTPClient(_FakeResponse(401, text="unauthorized"))

        with pytest.raises(DeepSeekError) as excinfo:
            await client.chat(client=http)  # type: ignore[arg-type]

        assert excinfo.value.status_code == 401
        assert excinfo.value.retryable is False

    @pytest.mark.asyncio
    async def test_success_clears_error(self) -> None:
        client = _make_client()
        http = _FakeHTTPClient(_FakeResponse(200, payload=_success_payload("你好")))

        await client.chat(client=http)  # type: ignore[arg-type]

        assert client.error is None
        assert client.response_content == "你好"

    @pytest.mark.asyncio
    async def test_failure_resets_previous_response(self) -> None:
        """第一次成功后第二次失败：上一次的响应不得残留。"""
        client = _make_client()

        await client.chat(
            client=_FakeHTTPClient(_FakeResponse(200, payload=_success_payload("第一次")))  # type: ignore[arg-type]
        )
        assert client.response_content == "第一次"
        assert client.error is None

        with pytest.raises(DeepSeekError):
            await client.chat(
                client=_FakeHTTPClient(httpx.ConnectError("conn reset"))  # type: ignore[arg-type]
            )

        assert client.response_ai_message is None
        assert client.response_content == ""
        assert client.error is not None
        assert client.error.kind == "connection"


#######################################################################################################################################
# 批量通讯：返回对齐的失败列表
#######################################################################################################################################
class _FakeChatClient:
    """仅满足 batch_chat 使用面的假 client。"""

    def __init__(self, label: str, error: Optional[DeepSeekError] = None):
        self.label = label
        self.error = error

    async def chat(self, client: Any = None) -> None:
        if self.error is not None:
            raise self.error


class TestBatchChatReturn:
    @pytest.mark.asyncio
    async def test_returns_aligned_failures(self) -> None:
        ok = _FakeChatClient("角色.A")
        timeout = DeepSeekError("角色.B", "timeout", kind="timeout")
        bad = _FakeChatClient("角色.B", error=timeout)

        errors = await batch_chat([ok, bad])  # type: ignore[list-item]

        assert errors == [None, timeout]
        assert errors[1] is bad.error

    @pytest.mark.asyncio
    async def test_empty_clients_returns_empty(self) -> None:
        assert await batch_chat([]) == []

    @pytest.mark.asyncio
    async def test_non_deepseek_exception_is_wrapped(self) -> None:
        """chat() 之外抛出的 BaseException 也应转成 DeepSeekError 返回，不丢失。"""

        class _BoomClient:
            label = "角色.C"
            error = None

            async def chat(self, client: Any = None) -> None:
                raise RuntimeError("unexpected")

        errors = await batch_chat([_BoomClient()])  # type: ignore[list-item]
        assert len(errors) == 1
        assert isinstance(errors[0], DeepSeekError)
        assert "RuntimeError" in str(errors[0])


#######################################################################################################################################
# 批量通讯：信号量限并发
#######################################################################################################################################
class _ConcurrencyProbeClient:
    """记录同时执行 chat() 的峰值数量。"""

    def __init__(self, label: str, tracker: Dict[str, int]):
        self.label = label
        self.error: Optional[DeepSeekError] = None
        self._tracker = tracker

    async def chat(self, client: Any = None) -> None:
        self._tracker["current"] += 1
        self._tracker["max"] = max(self._tracker["max"], self._tracker["current"])
        await asyncio.sleep(0.02)
        self._tracker["current"] -= 1


class TestBatchChatConcurrency:
    @pytest.mark.asyncio
    async def test_inflight_requests_are_bounded(self) -> None:
        tracker = {"current": 0, "max": 0}
        clients: List[Any] = [
            _ConcurrencyProbeClient(f"c{i}", tracker) for i in range(5)
        ]

        errors = await batch_chat(clients, max_concurrency=2)

        assert errors == [None, None, None, None, None]
        assert tracker["max"] <= 2
        assert tracker["current"] == 0

    @pytest.mark.asyncio
    async def test_max_concurrency_one_serializes(self) -> None:
        tracker = {"current": 0, "max": 0}
        clients: List[Any] = [
            _ConcurrencyProbeClient(f"c{i}", tracker) for i in range(3)
        ]

        await batch_chat(clients, max_concurrency=1)

        assert tracker["max"] == 1
