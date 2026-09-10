"""回合开始页面命令：info / round。"""

from typing import List

from loguru import logger

from ..models import CombatRoom, CombatState
from .app import GameClient
from .cmd_combat import load_combat_overview
from .combat_data_access import get_dungeon_room, is_mock_mode
from .utils import display_name


async def build_round_start_info_text(game_client: GameClient) -> str:
    """战斗宏观状态 + 回合/抓牌状态 + 场景角色有效属性。"""
    logger.info(f"build_round_start_info_text: mock={is_mock_mode(game_client)}")
    try:
        combat, stage_name, macro_lines, actor_lines = await load_combat_overview(
            game_client
        )
    except Exception as e:
        logger.error(f"build_round_start_info_text: 加载失败 error={e}")
        return f"[bold red]❌ 加载回合状态失败: {e}[/]"

    round_lines: List[str] = []
    if combat.state != CombatState.ONGOING:
        round_lines.append(
            f"[yellow]⚠️ 当前战斗状态：{combat.state.name}（本页预期 ONGOING）[/]"
        )
        round_lines.append("")

    round_lines.append(
        "[bold yellow]── 回合状态 ─────────────────────────────────────[/]"
    )
    round_lines.append(f"  场景：   {display_name(stage_name)}")
    round_lines.append(f"  当前局数： [bold]{len(combat.rounds)}[/]")

    latest = combat.latest_round
    if latest is None:
        round_lines.append("  [dim]（尚无回合，输入 /draw 开新回合并抓牌）[/]")
    else:
        draw_tag = "[green]是[/]" if latest.draw_completed else "[yellow]否[/]"
        complete_tag = "[green]是[/]" if latest.is_completed else "[yellow]否[/]"
        current_actor = latest.current_actor or "[dim]（无）[/]"
        if latest.action_order:
            order = "  →  ".join(latest.action_order)
        else:
            order = "[dim]（无）[/]"
        if latest.completed_actors:
            completed = "、".join(latest.completed_actors)
        else:
            completed = "[dim]（无）[/]"

        round_lines.append(f"  已抽牌： {draw_tag}")
        round_lines.append(f"  回合已结束： {complete_tag}")
        round_lines.append(f"  当前 turn： [bold yellow]{current_actor}[/]")
        round_lines.append(f"  行动顺序： {order}")
        round_lines.append(f"  已出手角色： {completed}")
        if latest.draw_completed:
            round_lines.append("  [dim]本回合已抓牌，可 /hand 查看双方手牌与能量。[/]")
        else:
            round_lines.append("  [dim]尚未抓牌，输入 /draw 抓牌。[/]")

    lines: List[str] = [*macro_lines, ""]
    lines.extend(round_lines)
    lines.append("")
    lines.extend(actor_lines)
    return "\n".join(lines)


async def build_round_detail_text(game_client: GameClient, round_number: int) -> str:
    """查阅指定回合（1-based 序号）的完整信息，返回可写入正文区的富文本字符串。"""
    logger.info(
        f"build_round_detail_text: mock={is_mock_mode(game_client)} "
        f"round_number={round_number}"
    )
    try:
        room_resp = await get_dungeon_room(game_client)
        room = room_resp.room
        assert isinstance(room, CombatRoom), f"当前房间不是战斗房间：type={room.type}"
        combat = room.combat
    except Exception as e:
        logger.error(f"build_round_detail_text: 加载失败 error={e}")
        return f"[bold red]❌ 加载回合详情失败: {e}[/]"

    if round_number < 1 or round_number > len(combat.rounds):
        return (
            f"[yellow]无效的回合序号：{round_number}，"
            f"当前共 {len(combat.rounds)} 回合（/info 查看总数）。[/]"
        )

    round_obj = combat.rounds[round_number - 1]

    lines: List[str] = []
    lines.append(
        f"[bold yellow]── 第 {round_number} 回合详情 ──────────────────────[/]"
    )
    complete_tag = "[green]是[/]" if round_obj.is_completed else "[yellow]否[/]"
    draw_tag = "[green]是[/]" if round_obj.draw_completed else "[yellow]否[/]"
    current_actor = round_obj.current_actor or "[dim]（无）[/]"
    lines.append(f"  回合已完成： {complete_tag}")
    lines.append(f"  抽牌已完成： {draw_tag}")
    lines.append(f"  当前 turn： [bold yellow]{current_actor}[/]")

    if round_obj.action_order:
        lines.append(f"  行动顺序： {'  →  '.join(round_obj.action_order)}")
    else:
        lines.append("  行动顺序： [dim]（无）[/]")

    if round_obj.completed_actors:
        lines.append(f"  已出手角色： {'、'.join(round_obj.completed_actors)}")
    else:
        lines.append("  已出手角色： [dim]（无）[/]")

    lines.append(f"  消耗品使用次数： [bold]{round_obj.consumable_use_count}[/]")
    lines.append(f"  装备使用次数：   [bold]{round_obj.gear_equip_count}[/]")
    lines.append("")

    def _render_list(title: str, entries: List[str]) -> None:
        lines.append(f"[bold cyan]── {title} ──[/]")
        if entries:
            for entry in entries:
                lines.append(f"  {entry}")
        else:
            lines.append("  [dim]（无）[/]")
        lines.append("")

    _render_list("出牌日志", round_obj.cards_log)
    _render_list("出牌叙事", round_obj.cards_narrative)
    _render_list("消耗品日志", round_obj.consumable_log)
    _render_list("消耗品叙事", round_obj.consumable_narrative)
    _render_list("装备日志", round_obj.gear_log)
    _render_list("装备叙事", round_obj.gear_narrative)

    return "\n".join(lines)
