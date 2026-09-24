"""AI 代理的服务器 API 走查 CLI。

定位：取代原 TUI，作为「后端开发者/代理走查服务器 API」的入口。
- 一次性进程：每次调用 = 一次 HTTP 请求（+ 必要时等待任务），无 TTY、无界面。
- 状态在服务端内存里；本脚本不缓存世界状态，只按参数寻址（--user/--game）。
- 输出统一为 JSON；HTTP 4xx/5xx 的 detail 原样透出，并以非零退出码结束。

典型用法：
    export AI_RPG_API_HOST=127.0.0.1 AI_RPG_API_PORT=8000
    uv run python scripts/run_agent_api.py login --user alice --game Game1
    uv run python scripts/run_agent_api.py new-game --user alice --game Game1
    uv run python scripts/run_agent_api.py status --user alice --game Game1
    uv run python scripts/run_agent_api.py home enter-dungeon --user alice --game Game1 --dungeon 副本.坍塌庙祠

HTTPS / JWT（连接层集中在一处）：
    --server-scheme https  （或 AI_RPG_API_SCHEME）
    --server-verify false  （自签证书；或传 CA bundle 路径 / AI_RPG_API_VERIFY）
    --token <jwt>          （或 AI_RPG_API_TOKEN，注入 Authorization: Bearer）

日志：``logs/run_agent_api_<timestamp>.log``（DEBUG；控制台级别由 AI_RPG_API_LOG_LEVEL 决定）。
命令分组：home / dungeon / opening / combat；`status` 会同时给出 suggested_actions。
"""

import asyncio
import datetime
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

import click
import httpx
from loguru import logger

from ai_rpg.api_agent.config import server_config
from ai_rpg.api_agent.flow import suggest_actions
from ai_rpg.api_agent.server_client import (
    compact_context,
    dungeon_advance_stage,
    dungeon_combat_collect_loot,
    dungeon_combat_draw_cards,
    dungeon_combat_equip_gear,
    dungeon_combat_init,
    dungeon_combat_pass_turn,
    dungeon_combat_play_cards,
    dungeon_combat_retreat,
    dungeon_combat_use_consumable,
    dungeon_exit,
    dungeon_opening_generate_spoils,
    dungeon_opening_init,
    dungeon_opening_pick_spoils_card,
    fetch_blueprint_list,
    fetch_dungeon_list,
    home_advance,
    home_craft_consumable,
    home_craft_costume_item,
    home_craft_gear_item,
    home_enter_dungeon,
    home_generate_dungeon,
    home_item_move_to_inventory,
    home_item_move_to_storage,
    home_remove_costume,
    home_roster_add,
    home_roster_remove,
    home_speak,
    home_switch_stage,
    home_wear_costume,
    login,
    logout,
    new_game,
    watch_task_until_done,
)
from ai_rpg.api_agent.status import build_status
from ai_rpg.paths import LOGS_DIR


########################################################################################################################
# 日志
########################################################################################################################
def _setup_logger() -> Path:
    """配置本进程日志：stderr 控制台 + ``logs/run_agent_api_<timestamp>.log`` 归档。

    - 控制台级别由 ``AI_RPG_API_LOG_LEVEL`` 控制（默认 WARNING，避免污染 agent 终端）；
    - 文件始终记录 DEBUG；文件名带秒级时间戳，与 run_game_server / run_agent_game 一致。
    注意：日志只写 stderr/文件，stdout 始终留给 JSON 结果。
    """
    logger.remove()
    console_level = os.environ.get("AI_RPG_API_LOG_LEVEL", "WARNING")
    logger.add(
        sys.stderr,
        level=console_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = LOGS_DIR / f"run_agent_api_{timestamp}.log"
    logger.add(log_file, level="DEBUG")
    return log_file


def _parse_verify(value: str) -> Union[bool, str]:
    """把 ``--server-verify`` 解析为 httpx 的 verify 参数。

    ``true/false``（大小写不敏感）→ bool；其余按 CA bundle 路径原样返回。
    """
    normalized = value.strip().lower()
    if normalized in ("false", "0", "no", "off"):
        return False
    if normalized in ("true", "1", "yes", "on", ""):
        return True
    return value


########################################################################################################################
# 输出与运行辅助
########################################################################################################################
def _emit(payload: Dict[str, Any], exit_code: int = 0) -> None:
    """把结果以 JSON 打印到 stdout；非零退出码用于让调用方/代理感知失败。"""
    click.echo(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    if exit_code != 0:
        sys.exit(exit_code)


def _error_payload(action: str, error: Exception) -> Dict[str, Any]:
    """把异常转成结构化错误，HTTP 错误透出 status_code 与 detail。"""
    if isinstance(error, httpx.HTTPStatusError):
        detail: Any
        try:
            detail = error.response.json().get("detail")
        except Exception:
            detail = error.response.text
        return {
            "ok": False,
            "action": action,
            "status_code": error.response.status_code,
            "detail": detail,
            "error": str(error),
        }
    return {
        "ok": False,
        "action": action,
        "error_type": type(error).__name__,
        "error": str(error),
    }


def _run(action: str, coro: Any) -> None:
    logger.info(f"执行动作: {action}")
    try:
        result = asyncio.run(coro)
    except Exception as error:  # noqa: BLE001 - 顶层兜底，转为结构化错误
        logger.error(f"动作失败: {action}: {type(error).__name__}: {error}")
        _emit(_error_payload(action, error), exit_code=1)
        return
    logger.info(f"动作成功: {action}")
    _emit({"ok": True, "action": action, "result": result})


async def _await_task(resp: Any) -> Dict[str, Any]:
    """统一处理「返回 job_id 的异步动作」：自动等待任务终态。"""
    snapshot = await watch_task_until_done(resp.job_id)
    return {
        "job_id": resp.job_id,
        "message": getattr(resp, "message", None),
        "status": snapshot.status.value,
    }


def _sync_result(resp: Any) -> Dict[str, Any]:
    """统一处理同步动作：返回其 message（若有）。"""
    return {"message": getattr(resp, "message", None)}


########################################################################################################################
# Click 选项装饰器
########################################################################################################################
def identity_options(func: Any) -> Any:
    """为命令加上 --user/--game（支持环境变量，默认从环境读取，便于一次导出多次调用）。"""
    func = click.option(
        "--game", envvar="AI_RPG_GAME", required=True, help="游戏名（蓝图名）"
    )(func)
    func = click.option("--user", envvar="AI_RPG_USER", required=True, help="用户名")(
        func
    )
    return func


########################################################################################################################
# 主命令组
########################################################################################################################
@click.group()
@click.option(
    "--server-host",
    envvar="AI_RPG_API_HOST",
    required=True,
    help="游戏服务器地址（或设 AI_RPG_API_HOST）",
)
@click.option(
    "--server-port",
    envvar="AI_RPG_API_PORT",
    type=int,
    required=True,
    help="游戏服务器端口（或设 AI_RPG_API_PORT）",
)
@click.option(
    "--server-scheme",
    envvar="AI_RPG_API_SCHEME",
    type=click.Choice(["http", "https"]),
    default="http",
    show_default=True,
    help="协议（或设 AI_RPG_API_SCHEME）",
)
@click.option(
    "--server-verify",
    envvar="AI_RPG_API_VERIFY",
    default="true",
    show_default=True,
    help="TLS 校验：true/false 或 CA bundle 路径（或设 AI_RPG_API_VERIFY）",
)
@click.option(
    "--token",
    envvar="AI_RPG_API_TOKEN",
    default=None,
    help="JWT 鉴权 Bearer token（或设 AI_RPG_API_TOKEN）",
)
@click.pass_context
def main(
    ctx: click.Context,
    server_host: str,
    server_port: int,
    server_scheme: str,
    server_verify: str,
    token: Optional[str],
) -> None:
    """AI 代理的服务器 API 走查 CLI。"""
    server_config.host = server_host
    server_config.port = server_port
    server_config.scheme = server_scheme
    server_config.verify = _parse_verify(server_verify)
    server_config.auth_token = token
    log_file = _setup_logger()
    logger.info(
        f"命令={ctx.invoked_subcommand} 目标={server_config.base_url} "
        f"TLS校验={server_config.verify} 鉴权={'bearer' if token else 'none'} "
        f"日志={log_file}"
    )


########################################################################################################################
# 顶层命令
########################################################################################################################
@main.command("login")
@identity_options
def login_cmd(user: str, game: str) -> None:
    """登录并在服务端创建房间（注意：会清掉该 user 已有房间）。"""

    async def go() -> Dict[str, Any]:
        return {"message": await login(user, game)}

    _run("login", go())


@main.command("logout")
@identity_options
def logout_cmd(user: str, game: str) -> None:
    """登出并销毁服务端房间。"""

    async def go() -> Dict[str, Any]:
        return {"message": await logout(user, game)}

    _run("logout", go())


@main.command("new-game")
@identity_options
def new_game_cmd(user: str, game: str) -> None:
    """新建游戏（家园态）。需先 login。"""

    async def go() -> Dict[str, Any]:
        resp = await new_game(user, game)
        return {
            "message": "新游戏已创建",
            "player_session": resp.player_session.model_dump(mode="json"),
            "blueprint": resp.blueprint.name,
        }

    _run("new-game", go())


@main.command("status")
@identity_options
@click.option(
    "--actor", default=None, help="显式指定玩家角色名（默认按 PlayerComponent 反查）"
)
@click.option(
    "--messages-since",
    type=int,
    default=0,
    show_default=True,
    help="会话消息起始 sequence_id（0=全量）",
)
def status_cmd(user: str, game: str, actor: Optional[str], messages_since: int) -> None:
    """观测当前世界状态，并给出 suggested_actions。"""

    async def go() -> Dict[str, Any]:
        snapshot = await build_status(
            user, game, actor=actor, messages_since=messages_since
        )
        snapshot["suggested_actions"] = suggest_actions(snapshot)
        return snapshot

    _run("status", go())


@main.command("blueprint-list")
def blueprint_list_cmd() -> None:
    """列出可用蓝图。"""

    async def go() -> Any:
        resp = await fetch_blueprint_list()
        return resp.model_dump(mode="json")

    _run("blueprint-list", go())


@main.command("dungeon-list")
def dungeon_list_cmd() -> None:
    """列出可用副本。"""

    async def go() -> Any:
        resp = await fetch_dungeon_list()
        return resp.model_dump(mode="json")

    _run("dungeon-list", go())


@main.command("compact")
@identity_options
@click.option("--target", "target", required=True, help="要压缩记忆的实体名")
def compact_cmd(user: str, game: str, target: str) -> None:
    """手动压缩指定实体的 LLM 记忆。"""

    async def go() -> Dict[str, Any]:
        return await _await_task(await compact_context(user, game, target))

    _run("compact", go())


########################################################################################################################
# 家园命令组
########################################################################################################################
@main.group("home")
def home_group() -> None:
    """家园模式动作。"""


@home_group.command("advance")
@identity_options
@click.option(
    "--actor",
    "actors",
    multiple=True,
    required=True,
    help="要推进的角色名（可多次指定，至少一个）",
)
def home_advance_cmd(user: str, game: str, actors: Tuple[str, ...]) -> None:
    """触发家园剧情推进。"""

    async def go() -> Dict[str, Any]:
        return await _await_task(await home_advance(user, game, list(actors)))

    _run("home advance", go())


@home_group.command("speak")
@identity_options
@click.option("--target", "target", required=True, help="对话目标角色名")
@click.option("--content", required=True, help="对话内容")
def home_speak_cmd(user: str, game: str, target: str, content: str) -> None:
    """玩家与目标角色对话。"""

    async def go() -> Dict[str, Any]:
        return await _await_task(await home_speak(user, game, target, content))

    _run("home speak", go())


@home_group.command("switch-stage")
@identity_options
@click.option("--stage", "stage_name", required=True, help="目标场景名")
def home_switch_stage_cmd(user: str, game: str, stage_name: str) -> None:
    """切换玩家所在场景。"""

    async def go() -> Dict[str, Any]:
        return await _await_task(await home_switch_stage(user, game, stage_name))

    _run("home switch-stage", go())


@home_group.command("generate-dungeon")
@identity_options
def home_generate_dungeon_cmd(user: str, game: str) -> None:
    """生成新副本。"""

    async def go() -> Dict[str, Any]:
        return await _await_task(await home_generate_dungeon(user, game))

    _run("home generate-dungeon", go())


@home_group.command("enter-dungeon")
@identity_options
@click.option("--dungeon", "dungeon_name", required=True, help="副本名")
def home_enter_dungeon_cmd(user: str, game: str, dungeon_name: str) -> None:
    """传送进入指定副本（仅传送到首间，不初始化房间）。"""

    async def go() -> Dict[str, Any]:
        return _sync_result(await home_enter_dungeon(user, game, dungeon_name))

    _run("home enter-dungeon", go())


@home_group.command("roster-add")
@identity_options
@click.option("--member", "member_name", required=True, help="要加入队伍的角色名")
def home_roster_add_cmd(user: str, game: str, member_name: str) -> None:
    """把角色加入队伍。"""

    async def go() -> Dict[str, Any]:
        return _sync_result(await home_roster_add(user, game, member_name))

    _run("home roster-add", go())


@home_group.command("roster-remove")
@identity_options
@click.option("--member", "member_name", required=True, help="要移出队伍的角色名")
def home_roster_remove_cmd(user: str, game: str, member_name: str) -> None:
    """把角色移出队伍。"""

    async def go() -> Dict[str, Any]:
        return _sync_result(await home_roster_remove(user, game, member_name))

    _run("home roster-remove", go())


@home_group.command("item-to-inventory")
@identity_options
@click.option(
    "--item", "item_names", multiple=True, required=True, help="道具名（可多次）"
)
def home_item_to_inventory_cmd(
    user: str, game: str, item_names: Tuple[str, ...]
) -> None:
    """把道具从储物箱移入随身背包。"""

    async def go() -> Dict[str, Any]:
        return _sync_result(
            await home_item_move_to_inventory(user, game, list(item_names))
        )

    _run("home item-to-inventory", go())


@home_group.command("item-to-storage")
@identity_options
@click.option(
    "--item", "item_names", multiple=True, required=True, help="道具名（可多次）"
)
def home_item_to_storage_cmd(user: str, game: str, item_names: Tuple[str, ...]) -> None:
    """把道具从随身背包移入储物箱。"""

    async def go() -> Dict[str, Any]:
        return _sync_result(
            await home_item_move_to_storage(user, game, list(item_names))
        )

    _run("home item-to-storage", go())


@home_group.command("craft-consumable")
@identity_options
@click.option(
    "--material", "materials", multiple=True, required=True, help="材料名（可多次）"
)
def home_craft_consumable_cmd(user: str, game: str, materials: Tuple[str, ...]) -> None:
    """用储物箱材料合成消耗品。"""

    async def go() -> Dict[str, Any]:
        return await _await_task(
            await home_craft_consumable(user, game, list(materials))
        )

    _run("home craft-consumable", go())


@home_group.command("craft-gear")
@identity_options
@click.option(
    "--material", "materials", multiple=True, required=True, help="材料名（可多次）"
)
def home_craft_gear_cmd(user: str, game: str, materials: Tuple[str, ...]) -> None:
    """用储物箱材料锻造装备。"""

    async def go() -> Dict[str, Any]:
        return await _await_task(
            await home_craft_gear_item(user, game, list(materials))
        )

    _run("home craft-gear", go())


@home_group.command("craft-costume")
@identity_options
@click.option(
    "--material", "materials", multiple=True, required=True, help="材料名（可多次）"
)
def home_craft_costume_cmd(user: str, game: str, materials: Tuple[str, ...]) -> None:
    """用储物箱材料制作时装。"""

    async def go() -> Dict[str, Any]:
        return await _await_task(
            await home_craft_costume_item(user, game, list(materials))
        )

    _run("home craft-costume", go())


@home_group.command("wear-costume")
@identity_options
@click.option("--item", "item_name", required=True, help="时装名")
@click.option("--target", "target_name", required=True, help="目标角色名")
def home_wear_costume_cmd(
    user: str, game: str, item_name: str, target_name: str
) -> None:
    """为角色穿戴时装。"""

    async def go() -> Dict[str, Any]:
        return await _await_task(
            await home_wear_costume(user, game, item_name, target_name)
        )

    _run("home wear-costume", go())


@home_group.command("remove-costume")
@identity_options
@click.option("--target", "target_name", required=True, help="目标角色名")
def home_remove_costume_cmd(user: str, game: str, target_name: str) -> None:
    """为角色脱下当前时装。"""

    async def go() -> Dict[str, Any]:
        return await _await_task(await home_remove_costume(user, game, target_name))

    _run("home remove-costume", go())


########################################################################################################################
# 副本生命周期命令组
########################################################################################################################
@main.group("dungeon")
def dungeon_group() -> None:
    """副本生命周期动作。"""


@dungeon_group.command("exit")
@identity_options
def dungeon_exit_cmd(user: str, game: str) -> None:
    """退出副本，返回家园。"""

    async def go() -> Dict[str, Any]:
        return await _await_task(await dungeon_exit(user, game))

    _run("dungeon exit", go())


@dungeon_group.command("advance-stage")
@identity_options
def dungeon_advance_stage_cmd(user: str, game: str) -> None:
    """推进到下一关卡（战斗胜利后 / 开场房间已初始化后）。"""

    async def go() -> Dict[str, Any]:
        return _sync_result(await dungeon_advance_stage(user, game))

    _run("dungeon advance-stage", go())


########################################################################################################################
# 开场房间命令组
########################################################################################################################
@main.group("opening")
def opening_group() -> None:
    """开场房间动作。"""


@opening_group.command("init")
@identity_options
def opening_init_cmd(user: str, game: str) -> None:
    """初始化开场房间（叙事 + 牌库）。"""

    async def go() -> Dict[str, Any]:
        return await _await_task(await dungeon_opening_init(user, game))

    _run("opening init", go())


@opening_group.command("generate-spoils")
@identity_options
def opening_generate_spoils_cmd(user: str, game: str) -> None:
    """生成开场奖励候选（Spoils）。"""

    async def go() -> Dict[str, Any]:
        return await _await_task(await dungeon_opening_generate_spoils(user, game))

    _run("opening generate-spoils", go())


@opening_group.command("pick-spoils-card")
@identity_options
@click.option("--actor", "actor_name", required=True, help="领卡角色名")
@click.option("--card", "card_name", required=True, help="要领取的卡名")
def opening_pick_spoils_card_cmd(
    user: str, game: str, actor_name: str, card_name: str
) -> None:
    """从角色的 Spoils 领取一张卡加入其牌库。"""

    async def go() -> Dict[str, Any]:
        return await _await_task(
            await dungeon_opening_pick_spoils_card(user, game, actor_name, card_name)
        )

    _run("opening pick-spoils-card", go())


########################################################################################################################
# 战斗命令组
########################################################################################################################
@main.group("combat")
def combat_group() -> None:
    """战斗动作。"""


@combat_group.command("init")
@identity_options
def combat_init_cmd(user: str, game: str) -> None:
    """初始化战斗（进入 ONGOING）。"""

    async def go() -> Dict[str, Any]:
        return await _await_task(await dungeon_combat_init(user, game))

    _run("combat init", go())


@combat_group.command("draw-cards")
@identity_options
def combat_draw_cards_cmd(user: str, game: str) -> None:
    """开启新回合并为全体抓牌。"""

    async def go() -> Dict[str, Any]:
        return await _await_task(await dungeon_combat_draw_cards(user, game))

    _run("combat draw-cards", go())


@combat_group.command("play-cards")
@identity_options
@click.option("--actor", "actor_name", required=True, help="出牌角色名")
@click.option(
    "--card",
    "card_name",
    default="",
    help="卡名；怪物回合可留空，服务端自动决策",
)
@click.option("--target", "targets", multiple=True, help="目标实体名（可多次）")
def combat_play_cards_cmd(
    user: str, game: str, actor_name: str, card_name: str, targets: Tuple[str, ...]
) -> None:
    """让角色打出卡牌。"""

    async def go() -> Dict[str, Any]:
        return await _await_task(
            await dungeon_combat_play_cards(
                user, game, actor_name, card_name, list(targets)
            )
        )

    _run("combat play-cards", go())


@combat_group.command("pass-turn")
@identity_options
@click.option("--actor", "actor_name", required=True, help="过牌角色名")
def combat_pass_turn_cmd(user: str, game: str, actor_name: str) -> None:
    """让角色过牌（结束其回合，推进行动权）。"""

    async def go() -> Dict[str, Any]:
        return await _await_task(await dungeon_combat_pass_turn(user, game, actor_name))

    _run("combat pass-turn", go())


@combat_group.command("use-consumable")
@identity_options
@click.option("--item", "item_name", required=True, help="消耗品名")
@click.option("--target", "targets", multiple=True, help="目标实体名（可多次）")
def combat_use_consumable_cmd(
    user: str, game: str, item_name: str, targets: Tuple[str, ...]
) -> None:
    """使用背包内消耗品（队伍级，不推进行动权）。"""

    async def go() -> Dict[str, Any]:
        return await _await_task(
            await dungeon_combat_use_consumable(user, game, item_name, list(targets))
        )

    _run("combat use-consumable", go())


@combat_group.command("equip-gear")
@identity_options
@click.option("--item", "item_name", required=True, help="装备名")
def combat_equip_gear_cmd(user: str, game: str, item_name: str) -> None:
    """使用背包内装备（队伍级，不推进行动权）。"""

    async def go() -> Dict[str, Any]:
        return await _await_task(await dungeon_combat_equip_gear(user, game, item_name))

    _run("combat equip-gear", go())


@combat_group.command("collect-loot")
@identity_options
def combat_collect_loot_cmd(user: str, game: str) -> None:
    """收取战斗战利品（转入背包）。"""

    async def go() -> Dict[str, Any]:
        return _sync_result(await dungeon_combat_collect_loot(user, game))

    _run("combat collect-loot", go())


@combat_group.command("retreat")
@identity_options
def combat_retreat_cmd(user: str, game: str) -> None:
    """战斗撤退。"""

    async def go() -> Dict[str, Any]:
        return await _await_task(await dungeon_combat_retreat(user, game))

    _run("combat retreat", go())


if __name__ == "__main__":
    main()
