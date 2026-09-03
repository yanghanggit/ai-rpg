"""队伍管理命令：list / add / remove，供 HomeScreen 的 roster 系列命令调用。"""

from typing import List, Set

from loguru import logger

from ..models import PartyRosterComponent
from .server_client import (
    fetch_entities_details,
    fetch_stages_state,
    home_roster_add,
    home_roster_remove,
)
from .utils import display_name


async def _fetch_current_roster(
    user_name: str, game_name: str, player_actor_name: str
) -> Set[str]:
    """读取玩家实体的 PartyRosterComponent，取得当前队伍名单。"""
    resp = await fetch_entities_details(user_name, game_name, [player_actor_name])
    for entity in resp.entities:
        for comp in entity.components:
            if comp.name == PartyRosterComponent.__name__:
                return set(PartyRosterComponent(**comp.data).members)
    return set()


async def build_roster_list_text(
    user_name: str, game_name: str, player_actor: str
) -> str:
    """列出全部角色，已在队伍中的加 [✓] 标记，返回可写入正文区的富文本字符串。"""
    logger.info(
        f"build_roster_list_text: 查询队伍 user_name={user_name} game_name={game_name}"
    )
    try:
        stages_resp = await fetch_stages_state(user_name, game_name)

        # 收集全部场景中的全部角色（去重、保持首次出现顺序，排除主角本人）
        all_actors: List[str] = []
        seen: Set[str] = set()
        for actors in stages_resp.mapping.values():
            for actor in actors:
                if actor != player_actor and actor not in seen:
                    seen.add(actor)
                    all_actors.append(actor)

        current_roster = await _fetch_current_roster(user_name, game_name, player_actor)

        lines: List[str] = []
        lines.append(
            "[bold cyan]── 队伍成员列表 ──────────────────────────────────────[/]"
        )
        if not all_actors:
            lines.append("  [dim]（暂无角色）[/]")
        for i, actor in enumerate(all_actors, 1):
            marker = "[bold green][✓][/]" if actor in current_roster else "[ ]"
            lines.append(
                f"  [bold green]{i}.[/] {marker} [cyan]{display_name(actor)}[/]"
            )

        logger.info(
            f"build_roster_list_text: 成功 角色 {len(all_actors)} 个，"
            f"队伍 {len(current_roster)} 人"
        )
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"build_roster_list_text: 失败 error={e}")
        return f"[bold red]❌ 读取队伍信息失败: {e}[/]"


async def add_roster_member(user_name: str, game_name: str, member_name: str) -> str:
    """将角色加入队伍，返回成功或失败文本。"""
    logger.info(
        f"add_roster_member: 加入队伍 user_name={user_name} member_name={member_name}"
    )
    try:
        await home_roster_add(user_name, game_name, member_name)
    except Exception as e:
        logger.error(f"add_roster_member: 失败 member_name={member_name} error={e}")
        return f"[bold red]❌ 加入失败: {e}[/]"
    logger.info(f"add_roster_member: 成功 member_name={member_name}")
    return f"[bold green]✅ {display_name(member_name)} 已加入队伍[/]"


async def remove_roster_member(user_name: str, game_name: str, member_name: str) -> str:
    """将角色移出队伍，返回成功或失败文本。"""
    logger.info(
        f"remove_roster_member: 移出队伍 user_name={user_name} member_name={member_name}"
    )
    try:
        await home_roster_remove(user_name, game_name, member_name)
    except Exception as e:
        logger.error(f"remove_roster_member: 失败 member_name={member_name} error={e}")
        return f"[bold red]❌ 移除失败: {e}[/]"
    logger.info(f"remove_roster_member: 成功 member_name={member_name}")
    return f"[bold green]✅ {display_name(member_name)} 已从队伍移除[/]"
