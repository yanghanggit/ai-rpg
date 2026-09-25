"""家园玩家动作接口测试。

`HomePlayerActionType` 已被移除，`/speak` 与 `/switch_stage` 拆成两个独立 endpoint。
拆分后最容易回归的四点在这里锁定：

1. 新路径存在、旧路径消失（OpenAPI 契约）；
2. `target` / `content` / `stage_name` 是必填的强类型字段（不再是 `Dict[str, str]`）；
3. payload → `activate_*` 的参数映射正确；
4. 错误分支（未登录 / 动作失败 / 缺参）返回预期状态码。

这些用例**不需要数据库、也不需要真实服务器**：用 `dependency_overrides` 注入假
GameServer，并 patch 掉 `activate_*` 与 procrastinate 的 `defer_async`。
"""

import asyncio
from contextlib import asynccontextmanager, contextmanager
from typing import Any, AsyncGenerator, Dict, Iterator, Tuple, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_rpg.services.game_server_dependencies import get_game_server
from ai_rpg.services.home_api import home_api_router
from ai_rpg.services.home_tasks import execute_home_pipeline_task
from ai_rpg.services.room_error_handlers import register_room_error_handlers
from ai_rpg.services.task_dispatch import RoomBusyError

SPEAK_PATH = "/api/home/player/speak/v1/"
SWITCH_PATH = "/api/home/player/switch_stage/v1/"
LEGACY_PATH = "/api/home/player_action/v1/"


class _FakeGame:
    """满足 `_validate_player_at_home` 所需属性的最小游戏替身。"""

    is_player_in_home_stage = True


class _FakeRoom:
    def __init__(self, game: Any) -> None:
        self._lock = asyncio.Lock()
        self._dbg_game = game

    @property
    def game(self) -> Any:
        return self._dbg_game

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[Any, None]:
        async with self._lock:
            yield self


class _FakeGameServer:
    def __init__(self, room: Any) -> None:
        self._room = room

    def has_room(self, user_name: str) -> bool:
        return self._room is not None

    def get_room(self, user_name: str) -> Any:
        return self._room


def _build_app(game_server: Any) -> FastAPI:
    """只挂载家园路由的最小 app，避免引入 DB / 队列依赖。"""
    app = FastAPI()
    app.include_router(home_api_router)
    app.dependency_overrides[get_game_server] = lambda: game_server
    register_room_error_handlers(app)
    return app


def _resolve_ref(spec: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    ref = schema.get("$ref")
    if ref:
        schemas: Dict[str, Any] = spec["components"]["schemas"]
        return cast(Dict[str, Any], schemas[ref.split("/")[-1]])
    return schema


def _request_schema(spec: Dict[str, Any], path: str) -> Dict[str, Any]:
    schema = spec["paths"][path]["post"]["requestBody"]["content"]["application/json"][
        "schema"
    ]
    return _resolve_ref(spec, schema)


def _response_schema(spec: Dict[str, Any], path: str) -> Dict[str, Any]:
    schema = spec["paths"][path]["post"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    return _resolve_ref(spec, schema)


@contextmanager
def _patch_home_action(
    activate_name: str,
    activate_result: Tuple[bool, str],
    job_id: int = 123,
) -> Iterator[Tuple[MagicMock, AsyncMock]]:
    """替换 `activate_*` 与任务派发助手，隔离外部副作用。"""
    activate = MagicMock(return_value=activate_result)
    defer = AsyncMock(return_value=job_id)
    with (
        patch(f"ai_rpg.services.home_api.{activate_name}", activate),
        patch("ai_rpg.services.home_api.defer_room_task", defer),
    ):
        yield activate, defer


@pytest.fixture
def game() -> _FakeGame:
    return _FakeGame()


@pytest.fixture
def client(game: _FakeGame) -> TestClient:
    return TestClient(_build_app(_FakeGameServer(_FakeRoom(game))))


@pytest.fixture
def logged_out_client() -> TestClient:
    return TestClient(_build_app(_FakeGameServer(None)))


# ---------------------------------------------------------------------------
# OpenAPI 契约
# ---------------------------------------------------------------------------


def test_openapi_exposes_new_paths_and_drops_legacy() -> None:
    """新 endpoint 注册，旧的 player_action 路由必须消失。"""
    spec = _build_app(_FakeGameServer(None)).openapi()
    assert SPEAK_PATH in spec["paths"]
    assert SWITCH_PATH in spec["paths"]
    assert LEGACY_PATH not in spec["paths"]


def test_speak_request_fields_are_required_strings() -> None:
    """target/content 是强类型必填字段，不再是 arguments 字典。"""
    spec = _build_app(_FakeGameServer(None)).openapi()
    schema = _request_schema(spec, SPEAK_PATH)
    assert schema["properties"]["target"]["type"] == "string"
    assert schema["properties"]["content"]["type"] == "string"
    assert "target" in schema["required"]
    assert "content" in schema["required"]


def test_switch_stage_request_field_is_required_string() -> None:
    spec = _build_app(_FakeGameServer(None)).openapi()
    schema = _request_schema(spec, SWITCH_PATH)
    assert schema["properties"]["stage_name"]["type"] == "string"
    assert "stage_name" in schema["required"]


def test_responses_expose_integer_job_id() -> None:
    spec = _build_app(_FakeGameServer(None)).openapi()
    for path in (SPEAK_PATH, SWITCH_PATH):
        schema = _response_schema(spec, path)
        assert schema["properties"]["job_id"]["type"] == "integer"
        assert schema["properties"]["message"]["type"] == "string"


# ---------------------------------------------------------------------------
# 正常路径：payload → activate_* 映射
# ---------------------------------------------------------------------------


def test_speak_happy_path(client: TestClient, game: _FakeGame) -> None:
    with _patch_home_action("activate_speak_action", (True, "")) as (activate, defer):
        response = client.post(
            SPEAK_PATH,
            json={
                "user_name": "u1",
                "game_name": "g1",
                "target": "小明",
                "content": "你好",
            },
        )

    assert response.status_code == 200
    assert response.json()["job_id"] == 123
    # payload 字段必须按名字传给 activate，而不是塞进 arguments 字典
    activate.assert_called_once_with(game, target="小明", content="你好")
    defer.assert_awaited_once_with(execute_home_pipeline_task, user_name="u1")


def test_switch_stage_happy_path(client: TestClient, game: _FakeGame) -> None:
    with _patch_home_action("activate_switch_stage", (True, "")) as (activate, defer):
        response = client.post(
            SWITCH_PATH,
            json={"user_name": "u1", "game_name": "g1", "stage_name": "酒馆"},
        )

    assert response.status_code == 200
    assert response.json()["job_id"] == 123
    activate.assert_called_once_with(game, stage_name="酒馆")
    defer.assert_awaited_once_with(execute_home_pipeline_task, user_name="u1")


# ---------------------------------------------------------------------------
# 错误分支
# ---------------------------------------------------------------------------


def test_speak_returns_400_when_action_fails(client: TestClient) -> None:
    with _patch_home_action("activate_speak_action", (False, "目标角色不存在")) as (
        _activate,
        defer,
    ):
        response = client.post(
            SPEAK_PATH,
            json={
                "user_name": "u1",
                "game_name": "g1",
                "target": "幽灵",
                "content": "在吗",
            },
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "目标角色不存在"
    # 激活失败时不得派发 pipeline 任务
    defer.assert_not_awaited()


def test_switch_stage_returns_400_when_action_fails(client: TestClient) -> None:
    with _patch_home_action("activate_switch_stage", (False, "目标场景不存在")) as (
        _activate,
        defer,
    ):
        response = client.post(
            SWITCH_PATH,
            json={"user_name": "u1", "game_name": "g1", "stage_name": "虚空"},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "目标场景不存在"
    defer.assert_not_awaited()


def test_speak_returns_404_when_not_logged_in(logged_out_client: TestClient) -> None:
    response = logged_out_client.post(
        SPEAK_PATH,
        json={
            "user_name": "u1",
            "game_name": "g1",
            "target": "小明",
            "content": "你好",
        },
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "没有登录，请先登录"


def test_switch_stage_returns_404_when_not_logged_in(
    logged_out_client: TestClient,
) -> None:
    response = logged_out_client.post(
        SWITCH_PATH,
        json={"user_name": "u1", "game_name": "g1", "stage_name": "酒馆"},
    )
    assert response.status_code == 404


def test_speak_returns_409_when_room_busy(client: TestClient) -> None:
    """重复派发被 queueing_lock 拦截时返回 409。"""
    with (
        patch(
            "ai_rpg.services.home_api.activate_speak_action",
            MagicMock(return_value=(True, "")),
        ),
        patch(
            "ai_rpg.services.home_api.defer_room_task",
            AsyncMock(side_effect=RoomBusyError("u1")),
        ),
    ):
        response = client.post(
            SPEAK_PATH,
            json={
                "user_name": "u1",
                "game_name": "g1",
                "target": "小明",
                "content": "你好",
            },
        )

    assert response.status_code == 409
    assert response.json()["detail"] == "该房间已有任务在进行中，请稍后重试"


@pytest.mark.parametrize(
    "path,payload",
    [
        (SPEAK_PATH, {"user_name": "u1", "game_name": "g1", "content": "你好"}),
        (SPEAK_PATH, {"user_name": "u1", "game_name": "g1", "target": "小明"}),
        (SWITCH_PATH, {"user_name": "u1", "game_name": "g1"}),
    ],
)
def test_missing_required_field_returns_422(
    client: TestClient, path: str, payload: Dict[str, Any]
) -> None:
    response = client.post(path, json=payload)
    assert response.status_code == 422
