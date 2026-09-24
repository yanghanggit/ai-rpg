"""组件名清单接口测试。

`/api/components/v1/` 是前端 `scripts/genApi.mjs` 生成编译期组件名清单的唯一来源，
所以这里锁定两件事：清单与 `COMPONENT_TYPES` 注册表**完全一致**（不多不少），
且响应模型进入 OpenAPI（否则前端生成脚本取不到结构）。

用例不需要数据库 / 真实服务器：只挂载组件路由。
"""

from typing import Any, Dict, List

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_rpg.models import COMPONENT_TYPES
from ai_rpg.services.components_api import components_api_router

COMPONENTS_PATH = "/api/components/v1/"


def _build_app() -> FastAPI:
    """只挂载组件路由的最小 app，避免引入 DB / 队列依赖。"""
    app = FastAPI()
    app.include_router(components_api_router)
    return app


@pytest.fixture
def client() -> TestClient:
    return TestClient(_build_app())


def test_returns_registered_component_names(client: TestClient) -> None:
    """返回的清单与注册表键完全一致，且已排序。"""
    response = client.get(COMPONENTS_PATH)

    assert response.status_code == 200
    names: List[str] = response.json()["names"]
    assert names == sorted(COMPONENT_TYPES)


def test_response_model_in_openapi(client: TestClient) -> None:
    """响应模型进入 OpenAPI，前端生成脚本才能按结构解析。"""
    spec: Dict[str, Any] = client.get("/openapi.json").json()
    schema_ref = spec["paths"][COMPONENTS_PATH]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["$ref"]
    assert schema_ref == "#/components/schemas/ComponentNamesResponse"
