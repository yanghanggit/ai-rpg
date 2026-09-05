"""时装命令：list-worn / wear / unwear，供 HomeScreen 的时装系列命令调用。"""

from typing import List, Set

from loguru import logger

from ..models import (
    AppearanceComponent,
    ComponentSerialization,
    WornCostumeComponent,
)
from .server_client import (
    fetch_entities_details,
    fetch_entities_group,
    fetch_stages_state,
    home_remove_costume,
    home_wear_costume,
    watch_task_until_done,
)
from .utils import display_name


async def _fetch_all_actor_names(user_name: str, game_name: str) -> List[str]:
    """获取全部场景中的全部角色名（去重，保持首次出现顺序）。"""
    stages_resp = await fetch_stages_state(user_name, game_name)
    all_actors: List[str] = []
    seen: Set[str] = set()
    for actors in stages_resp.mapping.values():
        for actor in actors:
            if actor not in seen:
                seen.add(actor)
                all_actors.append(actor)
    return all_actors


async def build_worn_list_text(user_name: str, game_name: str) -> str:
    """列出所有已穿戴时装的角色及其外观，返回可写入正文区的富文本字符串。

    通过 /entities/.../group 按 WornCostumeComponent 快速查询已穿戴角色，
    服务端返回的实体序列化已包含全部组件（含 AppearanceComponent）。
    """
    logger.info(
        f"build_worn_list_text: 查询已穿戴角色 user_name={user_name} game_name={game_name}"
    )
    try:
        resp = await fetch_entities_group(
            user_name,
            game_name,
            all_of=[WornCostumeComponent.__name__],
            any_of=[],
            none_of=[],
        )
        if not resp.entities:
            return (
                "[bold yellow]── 已穿戴时装 ──────────────────────────────────────[/]\n"
                "  [dim]（当前无人穿戴时装）[/]"
            )

        lines: List[str] = []
        lines.append(
            "[bold yellow]── 已穿戴时装 ──────────────────────────────────────[/]"
        )
        for entity in resp.entities:
            appearance = None
            worn = None
            for comp in entity.components:
                if comp.name == AppearanceComponent.__name__:
                    appearance = AppearanceComponent(**comp.data)
                elif comp.name == WornCostumeComponent.__name__:
                    worn = WornCostumeComponent(**comp.data)
            if worn is None:
                continue
            lines.append(f"  [bold cyan]{display_name(entity.name)}[/]")
            if appearance is not None:
                lines.append(f"    [dim]基础体型:[/] {appearance.base_body}")
                lines.append(f"    [dim]当前外观:[/] {appearance.appearance}")
            else:
                lines.append("    [dim]（未持有 AppearanceComponent）[/]")
            lines.append(
                f"    [magenta]时装:[/] {worn.item.name} — {worn.item.description}"
            )

        logger.info(f"build_worn_list_text: 成功 已穿戴 {len(resp.entities)} 人")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"build_worn_list_text: 失败 error={e}")
        return f"[bold red]❌ 获取外观信息失败: {e}[/]"


async def wear_costume(
    user_name: str, game_name: str, actor_name: str, costume_name: str
) -> str:
    """为目标角色穿上时装（若已穿戴则由服务端交换），返回成功或失败文本。"""
    logger.info(
        f"wear_costume: 穿装 user_name={user_name} actor={actor_name} costume={costume_name}"
    )
    try:
        all_actors = await _fetch_all_actor_names(user_name, game_name)
        if actor_name not in all_actors:
            return (
                f"[yellow]角色 {display_name(actor_name)} 不存在，"
                f"可用 /browse 或 /stage 查看。[/]"
            )

        details_resp = await fetch_entities_details(user_name, game_name, [actor_name])
        comps: List[ComponentSerialization] = []
        for entity in details_resp.entities:
            if entity.name == actor_name:
                comps = entity.components
                break
        if not any(c.name == AppearanceComponent.__name__ for c in comps):
            return (
                f"[yellow]角色 {display_name(actor_name)} 无法穿戴时装"
                f"（缺少 AppearanceComponent）。[/]"
            )

        resp = await home_wear_costume(user_name, game_name, costume_name, actor_name)
        await watch_task_until_done(resp.job_id)
    except Exception as e:
        logger.error(f"wear_costume: 失败 actor={actor_name} error={e}")
        return f"[bold red]❌ 穿戴失败: {e}[/]"

    logger.info(f"wear_costume: 成功 actor={actor_name} costume={costume_name}")
    return (
        f"[bold green]✅ {display_name(actor_name)} 已穿戴「{costume_name}」"
        f"（若已有旧时装则已交换）[/]"
    )


async def remove_costume(user_name: str, game_name: str, actor_name: str) -> str:
    """卸下目标角色当前穿戴的时装，返回成功或失败文本。"""
    logger.info(f"remove_costume: 卸装 user_name={user_name} actor={actor_name}")
    try:
        all_actors = await _fetch_all_actor_names(user_name, game_name)
        if actor_name not in all_actors:
            return (
                f"[yellow]角色 {display_name(actor_name)} 不存在，"
                f"可用 /browse 或 /stage 查看。[/]"
            )

        details_resp = await fetch_entities_details(user_name, game_name, [actor_name])
        comps: List[ComponentSerialization] = []
        for entity in details_resp.entities:
            if entity.name == actor_name:
                comps = entity.components
                break
        if not any(c.name == AppearanceComponent.__name__ for c in comps):
            return (
                f"[yellow]角色 {display_name(actor_name)} 无法卸下时装"
                f"（缺少 AppearanceComponent）。[/]"
            )
        if not any(c.name == WornCostumeComponent.__name__ for c in comps):
            return f"[yellow]{display_name(actor_name)} 当前未穿戴时装。[/]"

        resp = await home_remove_costume(user_name, game_name, actor_name)
        await watch_task_until_done(resp.job_id)
    except Exception as e:
        logger.error(f"remove_costume: 失败 actor={actor_name} error={e}")
        return f"[bold red]❌ 卸下失败: {e}[/]"

    logger.info(f"remove_costume: 成功 actor={actor_name}")
    return f"[bold green]✅ {display_name(actor_name)} 已卸下时装[/]"
