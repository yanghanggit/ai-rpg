"""实体浏览器命令：生成全部实体详情文本，供 HomeScreen 的 /browse（/b）调用。"""

import json
from typing import List, Set

from loguru import logger

from .server_client import fetch_entities_details, fetch_stages_state
from .utils import display_name


async def build_entity_browser_text(
    user_name: str, game_name: str, player_actor: str
) -> str:
    """获取并渲染全部实体详情，返回可写入正文区的富文本字符串。

    相当于对实体浏览器中的每个实体（全部场景 + 全部角色）执行一次 _show_entity：
    列出每个实体的全部组件及组件数据（JSON）。

    Args:
        user_name: 用户名
        game_name: 游戏名称
        player_actor: 玩家角色名，用于在实体标题中标注玩家

    Returns:
        可直接写入 RichLog 的富文本字符串

    Raises:
        服务端请求失败时向上抛出异常，由调用方决定如何展示错误。
    """
    logger.info(
        f"build_entity_browser_text: 请求实体列表 user_name={user_name} game_name={game_name}"
    )
    stages_resp = await fetch_stages_state(user_name, game_name)
    stages = list(stages_resp.mapping.keys())

    # 按首次出现顺序收集去重后的全部角色
    seen: Set[str] = set()
    actors: List[str] = []
    for actor_list in stages_resp.mapping.values():
        for actor in actor_list:
            if actor not in seen:
                seen.add(actor)
                actors.append(actor)

    entity_names = stages + actors
    if not entity_names:
        return "[yellow]暂无实体数据。[/]"

    details_resp = await fetch_entities_details(user_name, game_name, entity_names)
    components_by_entity = {
        entity.name: entity.components for entity in details_resp.entities
    }

    lines: List[str] = []
    lines.append("[bold cyan]── 实体浏览器 ──────────────────────────────────────[/]")
    lines.append(f"[dim]共 {len(entity_names)} 个实体[/]")
    lines.append("")

    for name in entity_names:
        marker = "  [dim](玩家)[/]" if name == player_actor else ""
        lines.append(
            f"[bold yellow]── 实体：{display_name(name)} ──────────────────────────────────────[/]{marker}"
        )
        comps = components_by_entity.get(name, [])
        if not comps:
            lines.append("  [dim]（无组件）[/]")
        for comp in comps:
            data_str = json.dumps(comp.data, ensure_ascii=False, indent=2)
            lines.append(f"  [bold cyan][组件][/] [green]{comp.name}[/]")
            lines.append(f"[dim]{data_str}[/]")
        lines.append("")

    logger.info(f"build_entity_browser_text: 成功，实体 {len(entity_names)} 个")
    return "\n".join(lines)
