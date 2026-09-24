"""run_agent_api 的 SSE 任务等待回归测试。

重点覆盖历史 bug：TaskSnapshot 即使是**成功**也会序列化出 ``"error": null``，
因此不能以 ``"error" in data`` 判定失败——只有不带 ``status`` 字段的才是错误封套。
"""

from typing import Any, AsyncIterator, Iterator, List

import httpx
import pytest
from procrastinate.jobs import Status as ProcrastinateJobStatus

from ai_rpg.api_agent.config import server_config
from ai_rpg.api_agent.server_client import (
    TaskFailedError,
    watch_task_until_done,
)


@pytest.fixture(autouse=True)
def _configure_server() -> Iterator[None]:
    """base_url 要求 host/port 由外部注入，测试里给个占位值（不会真的发请求）。"""
    server_config.host = "127.0.0.1"
    server_config.port = 1
    yield


class _FakeResponse:
    def __init__(self, lines: List[str]) -> None:
        self._lines = lines

    def raise_for_status(self) -> None:
        return None

    async def aiter_lines(self) -> AsyncIterator[str]:
        for line in self._lines:
            yield line


class _FakeStream:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response

    async def __aenter__(self) -> _FakeResponse:
        return self._response

    async def __aexit__(self, *exc: Any) -> bool:
        return False


class _FakeClient:
    def __init__(self, lines: List[str]) -> None:
        self._lines = lines

    async def __aenter__(self) -> "_FakeClient":
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False

    def stream(self, *args: Any, **kwargs: Any) -> _FakeStream:
        return _FakeStream(_FakeResponse(self._lines))


class _ClientFactory:
    """替换 httpx.AsyncClient 的可调用工厂。"""

    def __init__(self, lines: List[str]) -> None:
        self._lines = lines

    def __call__(self, *args: Any, **kwargs: Any) -> _FakeClient:
        return _FakeClient(self._lines)


def _patch_client(monkeypatch: pytest.MonkeyPatch, lines: List[str]) -> None:
    # server_client 内部通过 httpx.AsyncClient 发请求，patch 同一模块对象即可生效。
    monkeypatch.setattr(httpx, "AsyncClient", _ClientFactory(lines))


async def test_success_snapshot_with_null_error_is_not_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """成功快照带 "error": null，必须正常返回而非抛 TaskFailedError。"""
    _patch_client(
        monkeypatch,
        ['data: {"job_id": 1, "status": "succeeded", "error": null}', ""],
    )
    record = await watch_task_until_done(1, timeout_seconds=5)
    assert record.job_id == 1
    assert record.status == ProcrastinateJobStatus.SUCCEEDED


async def test_failed_snapshot_raises_with_error_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_client(
        monkeypatch,
        ['data: {"job_id": 2, "status": "failed", "error": "boom"}', ""],
    )
    with pytest.raises(TaskFailedError) as exc:
        await watch_task_until_done(2, timeout_seconds=5)
    assert "boom" in str(exc.value)


async def test_error_envelope_task_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_client(monkeypatch, ['data: {"error": "task_not_found", "job_id": 3}', ""])
    with pytest.raises(TaskFailedError):
        await watch_task_until_done(3, timeout_seconds=5)


async def test_error_envelope_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_client(monkeypatch, ['data: {"error": "timeout", "job_id": 4}', ""])
    with pytest.raises(TimeoutError):
        await watch_task_until_done(4, timeout_seconds=5)
