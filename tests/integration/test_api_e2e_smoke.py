"""API 端到端冒烟测试（集成测试）。

启动真实游戏服务端（uvicorn 子进程），模拟 TUI 客户端走一遍核心 HTTP 链路，
验证：家园 → 副本（开场房间）→ 战斗房间 的完整流转，以及战斗动作的同步校验行为。

依赖：
- DEEPSEEK_API_KEY（真实 LLM 调用，较慢）
- 本地 .blueprints / .dungeons 数据文件（默认用 Game1 + 副本.坍塌庙祠）

默认跳过；显式启用：
    RUN_E2E=1 pytest -m integration tests/integration/test_api_e2e_smoke.py
"""

import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple, cast

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"

GAME = "Game1"
DUNGEON = "副本.坍塌庙祠"
MONSTER = "怪物.纸人"
INVALID_CARD = "不存在的卡牌XYZ"

pytestmark = [pytest.mark.integration, pytest.mark.slow]

if os.environ.get("RUN_E2E") != "1":
    pytest.skip(
        "真实服务器 e2e 冒烟测试默认跳过；设置 RUN_E2E=1 启用",
        allow_module_level=True,
    )


def _api_key_available() -> bool:
    if os.environ.get("DEEPSEEK_API_KEY"):
        return True
    env_file = ROOT / ".env"
    if env_file.exists():
        return "DEEPSEEK_API_KEY" in env_file.read_text(encoding="utf-8")
    return False


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _wait_until_ready(base_url: str, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(f"{base_url}/", timeout=5.0)
            if r.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError("游戏服务器未能在超时时间内就绪")


@pytest.fixture(scope="module")
def game_server_url() -> Iterator[str]:
    """启动真实游戏服务端子进程，yield base_url，测试结束后终止并清理。"""
    if not _api_key_available():
        pytest.skip("DEEPSEEK_API_KEY 不可用，跳过 API 冒烟测试")

    port = _find_free_port()
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "run_game_server:app",
        "--app-dir",
        str(SCRIPTS_DIR),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--log-level",
        "warning",
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        env=os.environ.copy(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        _wait_until_ready(base_url)
        yield base_url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        # 清理本次冒烟产生的世界快照
        worlds_dir = ROOT / ".worlds"
        if worlds_dir.exists():
            for child in worlds_dir.iterdir():
                if child.name.startswith("e2e-api-"):
                    shutil.rmtree(child, ignore_errors=True)


def _post(
    client: httpx.Client, path: str, payload: Dict[str, Any]
) -> Tuple[int, Dict[str, Any]]:
    r = client.post(path, json=payload)
    try:
        data = r.json()
    except Exception:
        data = {"raw": r.text}
    return r.status_code, data


def _get(
    client: httpx.Client, path: str, params: Optional[Dict[str, Any]] = None
) -> Tuple[int, Dict[str, Any]]:
    r = client.get(path, params=params)
    try:
        data = r.json()
    except Exception:
        data = {"raw": r.text}
    return r.status_code, data


def _poll_task(client: httpx.Client, job_id: str, timeout: float = 300.0) -> str:
    """轮询后台任务直到终态，返回 'completed' / 'failed'，超时则失败。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        code, data = _get(client, "/api/tasks/v1/status", params={"job_ids": job_id})
        if code == 200:
            tasks = data.get("tasks", [])
            if tasks:
                status = (tasks[0].get("status") or "").lower()
                if status == "completed":
                    return status
                if status == "failed":
                    pytest.fail(f"后台任务失败: {tasks[0].get('error')}")
        time.sleep(1)
    pytest.fail(f"后台任务 {job_id} 轮询超时")


def _get_hand_cards(
    client: httpx.Client, user: str, player_actor: str
) -> List[Dict[str, Any]]:
    code, data = _get(
        client,
        f"/api/entities/v1/{user}/{GAME}/details",
        params={"entities": [player_actor]},
    )
    assert code == 200, f"查询实体失败: {data}"
    for entity in data.get("entities", []):
        for comp in entity.get("components", []):
            if comp.get("name") == "HandComponent":
                return cast(List[Dict[str, Any]], comp.get("data", {}).get("cards", []))
    return []


def test_api_e2e_smoke(game_server_url: str) -> None:
    """核心链路冒烟：进副本 → 开场初始化 → 战斗初始化 → 抽牌 → 出牌（含非法出牌同步 400）。"""
    client = httpx.Client(base_url=game_server_url, timeout=300.0)
    user = f"e2e-api-{int(time.time())}"

    # 1. 登录建房间
    code, _ = _post(client, "/api/login/v1/", {"user_name": user, "game_name": GAME})
    assert code == 200

    # 2. 新建游戏（家园态）
    code, data = _post(
        client, "/api/game/new/v1/", {"user_name": user, "game_name": GAME}
    )
    assert code == 200
    player_actor = data.get("player_session", {}).get("actor")
    assert player_actor, f"new game 未返回 player_session.actor: {data}"

    # 3. 进入副本（仅传送，不初始化房间）
    code, _ = _post(
        client,
        "/api/home/enter_dungeon/v1/",
        {"user_name": user, "game_name": GAME, "dungeon_name": DUNGEON},
    )
    assert code == 200

    # 4. 开场房间初始化
    code, data = _post(
        client, "/api/dungeon/opening/init/v1/", {"user_name": user, "game_name": GAME}
    )
    assert code == 200
    assert data.get("job_id")
    _poll_task(client, data["job_id"])

    # 5. 推进到战斗房间
    code, _ = _post(
        client,
        "/api/dungeon/progress/advance_stage/v1/",
        {"user_name": user, "game_name": GAME},
    )
    assert code == 200

    # 6. 战斗初始化
    code, data = _post(
        client, "/api/dungeon/combat/init/v1/", {"user_name": user, "game_name": GAME}
    )
    assert code == 200
    assert data.get("job_id")
    _poll_task(client, data["job_id"])

    # 7. 全员抽牌
    code, data = _post(
        client,
        "/api/dungeon/combat/draw_cards/v1/",
        {"user_name": user, "game_name": GAME},
    )
    assert code == 200
    assert data.get("job_id")
    _poll_task(client, data["job_id"])

    # 8. 查询玩家手牌
    hand_cards = _get_hand_cards(client, user, player_actor)
    assert hand_cards, "抽牌后玩家应有手牌"

    # 9. 关键断言：非法出牌应在请求阶段同步返回 400（而非后台任务失败）
    code, data = _post(
        client,
        "/api/dungeon/combat/play_cards/v1/",
        {
            "user_name": user,
            "game_name": GAME,
            "actor_name": player_actor,
            "card_name": INVALID_CARD,
            "targets": [],
        },
    )
    assert code == 400, f"非法出牌应同步返回 400，实际 {code}: {data}"
    assert "找不到卡牌" in str(data.get("detail", "")), f"detail 异常: {data}"

    # 10. 合法出牌应正常启动后台任务并完成
    playable = [c for c in hand_cards if c.get("playable", True)]
    assert playable, "手牌中应存在可打出的卡牌"
    card = playable[0]
    targets: List[str] = [] if card.get("self_target") else [MONSTER]
    code, data = _post(
        client,
        "/api/dungeon/combat/play_cards/v1/",
        {
            "user_name": user,
            "game_name": GAME,
            "actor_name": player_actor,
            "card_name": card.get("name"),
            "targets": targets,
        },
    )
    assert code == 200, f"合法出牌应返回 200，实际 {code}: {data}"
    assert data.get("job_id")
    _poll_task(client, data["job_id"])
