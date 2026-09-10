"""战斗结算（POST_COMBAT）命令：info / loot / history / collect / exit / advance。

供 CombatPostScreen 复用。改变性动作返回 (是否成功, 展示文本)。
"""

from itertools import zip_longest
from typing import List, Tuple

from loguru import logger

from ..models import (
    LootComponent,
    CombatResult,
    CombatRoom,
    Round,
)
from .app import GameClient
from .cmd_combat import find_component_data, load_combat_overview
from .combat_data_access import (
    get_dungeon_room,
    get_dungeon_state,
    get_entities_details,
    is_mock_mode,
    resolve_identity,
)
from .mock_data import (
    simulate_mock_advance_stage,
    simulate_mock_collect_loot,
    simulate_mock_exit_dungeon,
)
from .server_client import (
    dungeon_advance_stage,
    dungeon_combat_collect_loot,
    dungeon_exit,
)
from .utils import display_name, render_item


###############################################################################################################################################
async def build_post_combat_info_text(game_client: GameClient) -> str:
    """战斗结算宏观状态（胜负结果 + 总局数）+ 场景角色摘要。"""
    logger.info(f"build_post_combat_info_text: mock={is_mock_mode(game_client)}")
    try:
        combat, _, macro_lines, actor_lines = await load_combat_overview(game_client)
    except Exception as e:
        logger.error(f"build_post_combat_info_text: 加载失败 error={e}")
        return f"[bold red]❌ 加载结算信息失败：{e}[/]"

    lines: List[str] = list(macro_lines)
    lines.append(f"  总局数： [bold]{len(combat.rounds)}[/]")

    banner = None
    if combat.result == CombatResult.WIN:
        banner = "[bold green]🏆 战斗结果：胜利！[/]"
    elif combat.result == CombatResult.LOSE:
        banner = "[bold red]💀 战斗结果：失败！[/]"
    if banner is not None:
        lines.append("")
        lines.append(banner)

    lines.append("")
    lines.extend(actor_lines)
    return "\n".join(lines)


###############################################################################################################################################
async def build_loot_text(game_client: GameClient) -> str:
    """查阅玩家身上的 LootComponent（本场战斗战利品）。"""
    _, _, actor_name = resolve_identity(game_client)
    logger.info(f"build_loot_text: mock={is_mock_mode(game_client)} actor={actor_name}")
    try:
        resp = await get_entities_details(game_client, [actor_name])
    except Exception as e:
        logger.error(f"build_loot_text: 加载失败 error={e}")
        return f"[bold red]❌ 加载战利品失败：{e}[/]"

    if not resp.entities:
        return f"[yellow]未找到角色：{actor_name}[/]"

    entity = resp.entities[0]
    loot_data = find_component_data(entity, LootComponent.__name__)
    lines: List[str] = []
    lines.append(f"[bold yellow]── {display_name(entity.name)} 的战利品 ──[/]")
    if loot_data is None:
        lines.append("  [dim]（本场战斗无战利品，或已收取）[/]")
    else:
        loot = LootComponent(**loot_data)
        if not loot.items:
            lines.append("  [dim]（战利品为空）[/]")
        else:
            lines.append(f"  共 [bold]{len(loot.items)}[/] 件战利品：")
            for item in loot.items:
                lines.append("  " + render_item(item))

    return "\n".join(lines)


###############################################################################################################################################
def _append_round_lines(
    lines: List[str], round_: Round, index: int, is_latest: bool
) -> None:
    """把单个 Round 的完整数据追加到 lines（供 /history 一次性列出全部回合）。"""
    prefix = "[bold magenta]▶ [/]" if is_latest else "  "
    completed_mark = (
        "[green]✓ 已完成[/]" if round_.is_completed else "[yellow]进行中[/]"
    )
    draw_mark = "[green]是[/]" if round_.draw_completed else "[yellow]否[/]"

    lines.append(f"{prefix}[bold cyan]第 {index} 局[/]  {completed_mark}")

    order = (
        "  →  ".join(round_.action_order) if round_.action_order else "[dim]（无）[/]"
    )
    completed = (
        "、".join(round_.completed_actors)
        if round_.completed_actors
        else "[dim]（无）[/]"
    )
    lines.append(f"    行动顺序：   {order}")
    lines.append(f"    已出手角色： {completed}")
    if round_.current_actor is not None:
        lines.append(
            f"    当前 turn：  [bold yellow]{display_name(round_.current_actor)}[/]"
        )
    lines.append(f"    抽牌已完成： {draw_mark}")
    lines.append(f"    消耗品使用次数： [bold]{round_.consumable_use_count}[/]")
    lines.append(f"    装备使用次数：   [bold]{round_.gear_equip_count}[/]")

    if round_.cards_log or round_.cards_narrative:
        lines.append("    [bold]出牌记录：[/]")
        for j, (combat_log, narrative) in enumerate(
            zip_longest(round_.cards_log, round_.cards_narrative), start=1
        ):
            lines.append(f"      [{j}] [dim]战斗：[/] {combat_log or '[dim]（无）[/]'}")
            lines.append(f"          [dim]叙事：[/] {narrative or '[dim]（无）[/]'}")

    if round_.consumable_log or round_.consumable_narrative:
        lines.append("    [bold]消耗品记录：[/]")
        for j, (combat_log, narrative) in enumerate(
            zip_longest(round_.consumable_log, round_.consumable_narrative),
            start=1,
        ):
            lines.append(f"      [{j}] [dim]战斗：[/] {combat_log or '[dim]（无）[/]'}")
            lines.append(f"          [dim]叙事：[/] {narrative or '[dim]（无）[/]'}")

    if round_.gear_log or round_.gear_narrative:
        lines.append("    [bold]装备记录：[/]")
        for j, (combat_log, narrative) in enumerate(
            zip_longest(round_.gear_log, round_.gear_narrative), start=1
        ):
            lines.append(f"      [{j}] [dim]战斗：[/] {combat_log or '[dim]（无）[/]'}")
            lines.append(f"          [dim]叙事：[/] {narrative or '[dim]（无）[/]'}")

    lines.append("")


###############################################################################################################################################
async def build_round_history_text(game_client: GameClient) -> str:
    """一次性列出全部回合（含日志/叙事），最新回合在最后。"""
    logger.info(f"build_round_history_text: mock={is_mock_mode(game_client)}")
    try:
        room_resp = await get_dungeon_room(game_client)
        room = room_resp.room
        assert isinstance(room, CombatRoom), f"当前房间不是战斗房间：type={room.type}"
        combat = room.combat
    except Exception as e:
        logger.error(f"build_round_history_text: 加载失败 error={e}")
        return f"[bold red]❌ 加载历史回合失败：{e}[/]"

    lines: List[str] = []
    lines.append(
        "[bold yellow]── 历史回合详情 ──────────────────────────────────────[/]"
    )
    lines.append("")
    if not combat.rounds:
        lines.append("  [dim]（尚无回合数据）[/]")
        return "\n".join(lines)

    last_index = len(combat.rounds)
    for i, round_ in enumerate(combat.rounds, start=1):
        _append_round_lines(lines, round_, i, is_latest=(i == last_index))

    return "\n".join(lines)


###############################################################################################################################################
async def collect_loot(game_client: GameClient) -> Tuple[bool, str]:
    """收取战利品（转入随身背包）。"""
    if is_mock_mode(game_client):
        logger.info("collect_loot: mock 模式，模拟收取战利品")
        return simulate_mock_collect_loot()

    user_name, game_name, _ = resolve_identity(game_client)
    try:
        resp = await dungeon_combat_collect_loot(user_name, game_name)
    except Exception as e:
        logger.error(f"collect_loot: 收取失败 error={e}")
        return False, f"[bold red]❌ 收取战利品失败：{e}[/]"
    return True, f"[bold green]✅ {resp.message}[/]"


###############################################################################################################################################
async def exit_dungeon(game_client: GameClient) -> Tuple[bool, str]:
    """退出副本，返回家园。"""
    if is_mock_mode(game_client):
        logger.info("exit_dungeon: mock 模式，模拟退出副本")
        return simulate_mock_exit_dungeon()

    user_name, game_name, _ = resolve_identity(game_client)
    try:
        resp = await dungeon_exit(user_name, game_name)
    except Exception as e:
        logger.error(f"exit_dungeon: 退出失败 error={e}")
        return False, f"[bold red]❌ 退出副本失败：{e}[/]"
    return True, f"[bold green]✅ {resp.message}[/]"


###############################################################################################################################################
async def advance_stage(game_client: GameClient) -> Tuple[bool, str]:
    """进入下一关（房间）。"""
    try:
        state_resp = await get_dungeon_state(game_client)
        dungeon = state_resp.dungeon
    except Exception as e:
        logger.error(f"advance_stage: 查询副本状态失败 error={e}")
        return False, f"[bold red]❌ 查询副本状态失败：{e}[/]"

    if dungeon.current_room_index + 1 >= len(dungeon.rooms):
        return False, "[yellow]当前已是副本最后一关，没有下一关可进入。[/]"

    if is_mock_mode(game_client):
        logger.info("advance_stage: mock 模式，模拟推进到下一关")
        return simulate_mock_advance_stage()

    user_name, game_name, _ = resolve_identity(game_client)
    try:
        resp = await dungeon_advance_stage(user_name, game_name)
    except Exception as e:
        logger.error(f"advance_stage: 推进失败 error={e}")
        return False, f"[bold red]❌ 推进到下一关失败：{e}[/]"
    return True, f"[bold green]✅ {resp.message}[/]"
