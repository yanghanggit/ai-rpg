"""DeepSeek 通讯层：错误模型、单次结果、批量与 dump 接线的单元测试。

新的契约是「预期内失败不抛异常，落在 `ChatCompletionResult.error` 上」，因此这里断言的是
结果对象，而不是某个有状态 client 上的残留字段。
"""

import asyncio
from pathlib import Path
from typing import Any, Dict, Optional, Union

import httpx
import pytest

from ai_rpg.deepseek import DEEPSEEK_SERVICE, DeepSeekClient, DeepSeekError
from ai_rpg.llm import ChatCompletionRequest, ChatCompletionResult, ChatError
from ai_rpg.llm.batch import batch_complete
from ai_rpg.models import SystemMessage


############################################################################################################
# 测试替身
############################################################################################################
class _FakeResponse:
    """模拟 httpx.Response 的最小面。"""

    def __init__(
        self, status_code: int, text: str = "", payload: Optional[Dict[str, Any]] = None
    ) -> None:
        self.status_code = status_code
        self.text = text
        self._payload = payload

    def json(self) -> Dict[str, Any]:
        assert self._payload is not None, "该响应不应被解析"
        return self._payload


class _FakeHttpClient:
    """模拟 httpx.AsyncClient：post() 按预设行为抛出或返回，支持 async with。"""

    def __init__(self, outcome: Union[BaseException, _FakeResponse]) -> None:
        self._outcome = outcome

    async def __aenter__(self) -> "_FakeHttpClient":
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        return None

    async def post(self, url: str, **kwargs: Any) -> _FakeResponse:
        if isinstance(self._outcome, BaseException):
            raise self._outcome
        return self._outcome


class _FakeService:
    """按请求 label 决定成功/失败的 service 替身。"""

    def __init__(self, fail_labels: Optional[set[str]] = None) -> None:
        self._fail_labels = fail_labels or set()

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResult:
        if request.label in self._fail_labels:
            return ChatCompletionResult(
                request=request,
                error=ChatError(request.label, "boom", kind="api", status_code=500),
            )
        return ChatCompletionResult(request=request)


class _ConcurrencyProbeService:
    """记录同时在飞的最大请求数。"""

    def __init__(self, tracker: Dict[str, int]) -> None:
        self._tracker = tracker

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResult:
        self._tracker["current"] += 1
        self._tracker["max"] = max(self._tracker["max"], self._tracker["current"])
        await asyncio.sleep(0.01)
        self._tracker["current"] -= 1
        return ChatCompletionResult(request=request)


class _ExplodingService:
    """chat() 直接抛异常，验证 batch 把意外异常收敛成结果。"""

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResult:
        raise RuntimeError("boom")


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


def _service(outcome: Union[BaseException, _FakeResponse]) -> DeepSeekClient:
    return DeepSeekClient(http_client_factory=lambda: _FakeHttpClient(outcome))


def _request(label: str = "测试", **kwargs: Any) -> ChatCompletionRequest:
    # dump=False：本文件多数用例只验证通讯结果，不应在 .chat_dumps/ 留文件
    kwargs.setdefault("dump", False)
    return ChatCompletionRequest(
        label=label,
        input_message="ping",
        messages=[SystemMessage(content="sys")],
        **kwargs,
    )


############################################################################################################
# ChatError.retryable 判定
############################################################################################################
class TestChatErrorRetryable:
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


############################################################################################################
# 单次通讯：失败落在 result.error，不抛异常
############################################################################################################
class TestChatFailureRecordedAsResult:
    @pytest.mark.asyncio
    async def test_timeout(self) -> None:
        result = await _service(httpx.TimeoutException("read timeout")).complete(
            _request()
        )

        assert result.error is not None
        assert result.error.kind == "timeout"
        assert result.error.retryable is True
        assert result.ai_message is None
        assert result.ok is False

    @pytest.mark.parametrize(
        "outcome",
        [
            httpx.ConnectError("refused"),
            httpx.ReadError("broken"),
        ],
    )
    @pytest.mark.asyncio
    async def test_connection_errors(self, outcome: Exception) -> None:
        result = await _service(outcome).complete(_request())

        assert result.error is not None
        assert result.error.kind == "connection"
        assert result.error.retryable is True

    @pytest.mark.parametrize(
        "status_code,retryable",
        [
            (400, False),
            (401, False),
            (402, False),
            (422, False),
            (429, True),
            (500, True),
        ],
    )
    @pytest.mark.asyncio
    async def test_http_error_status(self, status_code: int, retryable: bool) -> None:
        result = await _service(_FakeResponse(status_code, text="boom")).complete(
            _request()
        )

        assert result.error is not None
        assert result.error.kind == "api"
        assert result.error.status_code == status_code
        assert result.error.retryable is retryable

    @pytest.mark.asyncio
    async def test_success(self) -> None:
        result = await _service(
            _FakeResponse(200, payload=_success_payload("hi"))
        ).complete(_request())

        assert result.error is None
        assert result.ok is True
        assert result.content == "hi"
        assert result.finish_reason == "stop"
        assert result.tool_calls == ()
        assert result.usage is not None
        assert result.usage.total_tokens == 2
        assert result.ai_message is not None


############################################################################################################
# 无状态：同一个 service 复用不会串味
############################################################################################################
class TestServiceIsStateless:
    @pytest.mark.asyncio
    async def test_second_call_does_not_see_first_result(self) -> None:
        first = await _service(
            _FakeResponse(200, payload=_success_payload("A"))
        ).complete(_request("one"))
        assert first.content == "A"

        # 同一个 service 实例（默认工厂）连续调用，结果互不影响
        service = _service(_FakeResponse(200, payload=_success_payload("B")))
        await service.complete(_request("a"))
        second = await service.complete(_request("b"))

        assert second.content == "B"
        assert second.request.label == "b"
        assert second.error is None

    @pytest.mark.asyncio
    async def test_failure_then_success(self) -> None:
        service = DeepSeekClient(
            http_client_factory=lambda: _FakeHttpClient(httpx.TimeoutException("t"))
        )
        failed = await service.complete(_request())
        assert failed.error is not None

        # 换上能成功的工厂：service 本身不残留上一次的错误
        service = _service(_FakeResponse(200, payload=_success_payload("ok")))
        succeeded = await service.complete(_request())
        assert succeeded.error is None
        assert succeeded.content == "ok"


############################################################################################################
# batch：结果与请求同序、失败走 error、并发受限
############################################################################################################
class TestBatchChat:
    @pytest.mark.asyncio
    async def test_results_align_with_requests(self) -> None:
        requests = [_request(f"c{i}") for i in range(3)]
        results = await batch_complete(
            _FakeService(fail_labels={"c1"}), requests, max_concurrency=3
        )

        assert [r.label for r in results] == ["c0", "c1", "c2"]
        assert [r.ok for r in results] == [True, False, True]
        assert results[1].error is not None
        assert results[1].error.status_code == 500

    @pytest.mark.asyncio
    async def test_empty_requests(self) -> None:
        assert await batch_complete(_FakeService(), []) == []

    @pytest.mark.asyncio
    async def test_unexpected_exception_becomes_result_error(self) -> None:
        results = await batch_complete(_ExplodingService(), [_request("x")])

        assert len(results) == 1
        assert results[0].error is not None
        assert "RuntimeError" in str(results[0].error)

    @pytest.mark.asyncio
    async def test_concurrency_is_bounded(self) -> None:
        tracker = {"current": 0, "max": 0}
        requests = [_request(f"c{i}") for i in range(5)]

        results = await batch_complete(
            _ConcurrencyProbeService(tracker), requests, max_concurrency=2
        )

        assert all(r.ok for r in results)
        assert tracker["max"] <= 2
        assert tracker["current"] == 0


############################################################################################################
# chat dump 接线：是否落盘由 request.dump + 进程级开关共同决定
############################################################################################################
class TestChatDumpWiring:
    @pytest.mark.asyncio
    async def test_successful_chat_dumps_by_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("ai_rpg.llm.chat_dump.CHAT_DUMP_DIR", tmp_path)
        monkeypatch.delenv("AI_RPG_CHAT_DUMP_ENABLED", raising=False)

        request = ChatCompletionRequest(
            label="测试.落盘",
            input_message="ping",
            messages=[SystemMessage(content="sys")],
        )
        assert request.dump is True

        await _service(_FakeResponse(200, payload=_success_payload())).complete(request)

        files = list(tmp_path.glob("*.txt"))
        assert len(files) == 1
        assert "ping" in files[0].read_text(encoding="utf-8")

    @pytest.mark.asyncio
    async def test_dump_false_writes_nothing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("ai_rpg.llm.chat_dump.CHAT_DUMP_DIR", tmp_path)
        monkeypatch.delenv("AI_RPG_CHAT_DUMP_ENABLED", raising=False)

        request = _request()  # dump=False
        result = await _service(
            _FakeResponse(200, payload=_success_payload())
        ).complete(request)

        assert result.content == "hi"
        assert list(tmp_path.glob("*.txt")) == []

    @pytest.mark.asyncio
    async def test_failed_chat_dumps_nothing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """失败请求没有可供留痕的完整对话（只在成功后落盘）。"""
        monkeypatch.setattr("ai_rpg.llm.chat_dump.CHAT_DUMP_DIR", tmp_path)
        monkeypatch.delenv("AI_RPG_CHAT_DUMP_ENABLED", raising=False)

        request = ChatCompletionRequest(
            label="测试.失败",
            input_message="ping",
            messages=[SystemMessage(content="sys")],
        )
        await _service(_FakeResponse(500, text="boom")).complete(request)

        assert list(tmp_path.glob("*.txt")) == []


############################################################################################################
# 共用的默认实例
############################################################################################################
def test_default_service_is_a_deepseek_client() -> None:
    """默认实例是 provider 决策点，业务侧复用它而不是自己 new。"""
    assert isinstance(DEEPSEEK_SERVICE, DeepSeekClient)
