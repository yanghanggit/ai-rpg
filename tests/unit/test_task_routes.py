"""后台任务路由的输入校验测试。

回归背景：修复前 `/api/tasks/v1/status` 与 `/api/tasks/v1/watch/{job_id}` 都把 job_id
直接交给下游的 `int(job_id)`，传入非数字 id 会抛出未捕获的 ValueError：

  - `/status` → HTTP 500
  - `/watch`  → 响应头已发出，客户端只收到一个空的 SSE 流（静默失败，比 500 更难排查）

现在校验被提到契约层（FastAPI 的 `pattern`），非法输入在进入处理函数之前就被拦下，
并会写进 OpenAPI，契约因此是自我描述的。

这些用例**不需要数据库、也不需要真实服务器**：只挂载后台任务路由，校验失败发生在
访问 DB 之前。
"""

from typing import Any, Dict, List

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.ai_rpg.services.background_tasks import background_tasks_api_router

STATUS_PATH = "/api/tasks/v1/status"
WATCH_PATH = "/api/tasks/v1/watch/{job_id}"


def _build_app() -> FastAPI:
    """只挂载后台任务路由的最小 app，避免引入 DB / 队列依赖。"""
    app = FastAPI()
    app.include_router(background_tasks_api_router)
    return app


@pytest.fixture
def client() -> TestClient:
    return TestClient(_build_app())


def _get_parameter(spec: Dict[str, Any], path: str, name: str) -> Dict[str, Any]:
    parameters: List[Dict[str, Any]] = spec["paths"][path]["get"]["parameters"]
    for parameter in parameters:
        if parameter["name"] == name:
            return parameter
    raise AssertionError(f"OpenAPI 中缺少参数 {name}")


def test_status_rejects_non_numeric_job_id(client: TestClient) -> None:
    """单个非数字 id → 422（修复前是 500）"""
    response = client.get(STATUS_PATH, params={"job_ids": "abc"})
    assert response.status_code == 422


def test_status_rejects_mixed_valid_and_invalid_job_ids(client: TestClient) -> None:
    """合法与非法混合时整体 422（修复前是 500）"""
    response = client.get(STATUS_PATH, params={"job_ids": ["1", "abc"]})
    assert response.status_code == 422


def test_status_rejects_empty_job_id(client: TestClient) -> None:
    """空字符串 → 422（修复前是 400 + 自定义中文 detail）"""
    response = client.get(STATUS_PATH, params={"job_ids": ""})
    assert response.status_code == 422


def test_status_requires_job_ids(client: TestClient) -> None:
    """缺少必填参数 → 422"""
    response = client.get(STATUS_PATH)
    assert response.status_code == 422


def test_watch_rejects_non_numeric_job_id(client: TestClient) -> None:
    """路径参数同样受校验（修复前返回 200 + 空响应体）"""
    response = client.get("/api/tasks/v1/watch/abc")
    assert response.status_code == 422


def test_openapi_declares_job_id_pattern() -> None:
    """校验规则要写进 OpenAPI，契约才是自我描述的"""
    spec = _build_app().openapi()

    query = _get_parameter(spec, STATUS_PATH, "job_ids")
    assert query["schema"]["items"]["pattern"] == r"^\d+$"

    path_parameter = _get_parameter(spec, WATCH_PATH, "job_id")
    assert path_parameter["schema"]["pattern"] == r"^\d+$"
