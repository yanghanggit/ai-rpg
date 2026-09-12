"""任务路由的输入校验测试。

背景：job_id 直接就是 Procrastinate 的自增整数，路由层用 `int` 类型声明。
非整数输入（`abc` / 空串）由 FastAPI 在进入处理函数之前拦下并返回 422，
不会再出现 "非法 id 传进下游才抛 ValueError" 的 500 或 SSE 静默失败。

这些用例**不需要数据库、也不需要真实服务器**：只挂载任务路由，校验失败发生在
访问 DB 之前。
"""

from typing import Any, Dict, List

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.ai_rpg.services.tasks_api import tasks_api_router

STATUS_PATH = "/api/tasks/v1/status"
WATCH_PATH = "/api/tasks/v1/watch/{job_id}"


def _build_app() -> FastAPI:
    """只挂载任务路由的最小 app，避免引入 DB / 队列依赖。"""
    app = FastAPI()
    app.include_router(tasks_api_router)
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
    """单个非整数字符串 id → 422"""
    response = client.get(STATUS_PATH, params={"job_ids": "abc"})
    assert response.status_code == 422


def test_status_rejects_mixed_valid_and_invalid_job_ids(client: TestClient) -> None:
    """合法与非法混合时整体 422"""
    response = client.get(STATUS_PATH, params={"job_ids": ["1", "abc"]})
    assert response.status_code == 422


def test_status_rejects_empty_job_id(client: TestClient) -> None:
    """空字符串 → 422"""
    response = client.get(STATUS_PATH, params={"job_ids": ""})
    assert response.status_code == 422


def test_status_requires_job_ids(client: TestClient) -> None:
    """缺少必填参数 → 422"""
    response = client.get(STATUS_PATH)
    assert response.status_code == 422


def test_watch_rejects_non_numeric_job_id(client: TestClient) -> None:
    """路径参数同样按整数校验，非整数 → 422"""
    response = client.get("/api/tasks/v1/watch/abc")
    assert response.status_code == 422


def test_openapi_declares_job_id_as_integer() -> None:
    """job_id 在 OpenAPI 中就是 integer，契约自我描述了 "不再是不透明字符串" 这一事实"""
    spec = _build_app().openapi()

    query = _get_parameter(spec, STATUS_PATH, "job_ids")
    assert query["schema"]["items"]["type"] == "integer"

    path_parameter = _get_parameter(spec, WATCH_PATH, "job_id")
    assert path_parameter["schema"]["type"] == "integer"
