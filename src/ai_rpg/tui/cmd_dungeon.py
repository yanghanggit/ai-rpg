"""副本命令：list-dungeons / dungeon / enter-dungeon / generate-dungeon。"""

from typing import List, Tuple

from loguru import logger

from ..models import ActorType, PartyRosterComponent
from .server_client import (
    TaskFailedError,
    fetch_dungeon_list,
    fetch_entities_details,
    home_enter_dungeon,
    home_generate_dungeon,
    watch_task_until_done,
)
from .utils import display_name


async def build_dungeon_list_text(
    user_name: str, game_name: str, player_actor: str
) -> str:
    """列出可用副本与当前队伍，返回可写入正文区的富文本字符串。"""
    logger.info(
        f"build_dungeon_list_text: 查询副本 user_name={user_name} game_name={game_name}"
    )
    lines: List[str] = []

    if player_actor:
        try:
            resp = await fetch_entities_details(user_name, game_name, [player_actor])
            members: List[str] = []
            for entity in resp.entities:
                for comp in entity.components:
                    if comp.name == PartyRosterComponent.__name__:
                        members = list(PartyRosterComponent(**comp.data).members)
                        break
            roster = [player_actor] + members
            lines.append(
                "[bold yellow]── 当前队伍 ──────────────────────────────────────[/]"
            )
            for member in roster:
                tag = "  [bold magenta][玩家][/]" if member == player_actor else ""
                lines.append(f"  · [bold cyan]{display_name(member)}[/]{tag}")
            lines.append("")
        except Exception as e:
            logger.warning(f"build_dungeon_list_text: 读取队伍失败 error={e}")

    try:
        dungeons = (await fetch_dungeon_list()).dungeons
    except Exception as e:
        logger.error(f"build_dungeon_list_text: 获取副本列表失败 error={e}")
        return f"[bold red]❌ 副本列表加载失败: {e}[/]"

    lines.append("[bold yellow]── 可用副本 ──────────────────────────────────────[/]")
    if not dungeons:
        lines.append("  [dim]（暂无可用副本）[/]")
    else:
        for i, dungeon in enumerate(dungeons, 1):
            preview = dungeon.profile[:40].replace("\n", " ")
            room_count = len(dungeon.rooms)
            lines.append(
                f"  [bold]{i}.[/] [bold cyan]{display_name(dungeon.name)}[/]"
                f"  [dim]{preview}…  ({room_count} 个房间)[/]"
            )
    lines.append("")
    lines.append(
        "[dim]可用 /dungeon @副本名 查看详情，/enter-dungeon @副本名 进入。[/]"
    )

    logger.info(f"build_dungeon_list_text: 成功 共 {len(dungeons)} 个副本")
    return "\n".join(lines)


async def build_dungeon_detail_text(dungeon_name: str) -> str:
    """查看指定副本详情，返回可写入正文区的富文本字符串。"""
    logger.info(f"build_dungeon_detail_text: 查看副本 dungeon={dungeon_name}")
    try:
        dungeons = (await fetch_dungeon_list()).dungeons
    except Exception as e:
        logger.error(f"build_dungeon_detail_text: 获取副本列表失败 error={e}")
        return f"[bold red]❌ 副本列表加载失败: {e}[/]"

    dungeon = next((d for d in dungeons if d.name == dungeon_name), None)
    if dungeon is None:
        return (
            f"[yellow]未找到副本：{display_name(dungeon_name)}，"
            f"可用 /list-dungeons 查看。[/]"
        )

    lines: List[str] = []
    lines.append(
        f"[bold yellow]── 副本：{display_name(dungeon.name)} ──────────────────────────────────────[/]"
    )
    lines.append(f"  [bold]整体设定：[/] {dungeon.profile}")
    lines.append(f"  [bold]房间数：[/]   {len(dungeon.rooms)}")
    lines.append("")

    for i, room in enumerate(dungeon.rooms, 1):
        stage = room.stage
        is_combat = any(actor.type == ActorType.MONSTER for actor in stage.actors)
        room_tag = "[bold red]⚔ 战斗[/]" if is_combat else "[dim cyan]○ 探索[/]"
        lines.append(
            f"  [bold cyan]房间 {i}：[/][green]{display_name(stage.name)}[/]  {room_tag}"
        )
        if is_combat:
            for actor in stage.actors:
                if actor.type == ActorType.MONSTER:
                    stats = actor.character_stats
                    lines.append(
                        f"    · [bold]{display_name(actor.name)}[/]"
                        f"  HP:[yellow]{stats.max_hp}[/]"
                        f"  ATK:[red]{stats.attack}[/]"
                        f"  DEF:[blue]{stats.defense}[/]"
                    )
        else:
            lines.append("    [dim]（无敌人）[/]")

    logger.info(f"build_dungeon_detail_text: 成功 dungeon={dungeon_name}")
    return "\n".join(lines)


async def generate_dungeon(user_name: str, game_name: str) -> str:
    """生成新副本，返回成功或失败文本。"""
    logger.info(
        f"generate_dungeon: 生成副本 user_name={user_name} game_name={game_name}"
    )
    try:
        resp = await home_generate_dungeon(user_name, game_name)
        task_id = resp.task_id
    except Exception as e:
        logger.error(f"generate_dungeon: 请求失败 error={e}")
        return f"[bold red]❌ 副本生成请求失败: {e}[/]"

    try:
        await watch_task_until_done(task_id)
        logger.info(f"generate_dungeon: 完成 task_id={task_id}")
        return "[bold green]✅ 副本生成完成，见 /list-dungeons。[/]"
    except TaskFailedError as e:
        logger.error(f"generate_dungeon: 失败 task_id={task_id} error={e}")
        return f"[bold red]❌ 副本生成失败: {e}[/]"
    except TimeoutError:
        logger.warning(f"generate_dungeon: 超时 task_id={task_id}")
        return "[bold yellow]⚠️ 副本生成超时，请检查服务器状态[/]"
    except Exception as e:
        logger.warning(f"generate_dungeon: 等待任务失败 error={e}")
        return f"[bold red]❌ 等待任务失败: {e}[/]"


async def enter_dungeon(
    user_name: str, game_name: str, dungeon_name: str
) -> Tuple[bool, str]:
    """进入指定副本，返回 (是否成功, 展示文本)。成功后由调用方导航到副本房间。"""
    logger.info(f"enter_dungeon: 进入副本 user_name={user_name} dungeon={dungeon_name}")
    try:
        dungeons = (await fetch_dungeon_list()).dungeons
        if not any(d.name == dungeon_name for d in dungeons):
            return False, (
                f"[yellow]未找到副本：{display_name(dungeon_name)}，"
                f"可用 /list-dungeons 查看。[/]"
            )
        await home_enter_dungeon(user_name, game_name, dungeon_name)
    except Exception as e:
        logger.error(f"enter_dungeon: 进入失败 dungeon={dungeon_name} error={e}")
        return False, f"[bold red]❌ 进入副本失败: {e}[/]"

    logger.info(f"enter_dungeon: 进入成功 dungeon={dungeon_name}")
    return True, f"[bold green]✅ 已进入副本：{dungeon_name}[/]"
