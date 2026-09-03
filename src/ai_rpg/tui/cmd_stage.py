"""当前场景命令：生成场景描述与角色外观文本，供 HomeScreen 的 /stage（/st）调用。"""

from typing import List, Optional

from loguru import logger

from ..models import AppearanceComponent, StageDescriptionComponent
from .server_client import fetch_entities_details, fetch_stages_state
from .utils import display_name


async def build_stage_view_text(
    user_name: str, game_name: str, player_actor: str
) -> str:
    """查看玩家当前所在场景的描述与场景内全部角色的外观，返回可写入正文区的富文本字符串。

    Args:
        user_name: 用户名
        game_name: 游戏名称
        player_actor: 玩家角色名，用于定位所在场景并标注玩家

    Returns:
        可直接写入 RichLog 的富文本字符串；若无法确定玩家所在场景，返回提示文本。

    Raises:
        服务端请求失败时向上抛出异常，由调用方决定如何展示错误。
    """
    logger.info(
        f"build_stage_view_text: 请求当前场景 user_name={user_name} game_name={game_name}"
    )
    stages_resp = await fetch_stages_state(user_name, game_name)

    stage_name: Optional[str] = None
    actor_names: List[str] = []
    for name, actors in stages_resp.mapping.items():
        if player_actor in actors:
            stage_name = name
            actor_names = actors
            break

    if stage_name is None:
        return "[yellow]无法确定玩家当前所在场景。[/]"

    details_resp = await fetch_entities_details(
        user_name, game_name, [stage_name] + actor_names
    )

    components_by_entity = {
        entity.name: entity.components for entity in details_resp.entities
    }

    lines: List[str] = []
    lines.append(
        f"[bold yellow]── 当前场景：{display_name(stage_name)} ──────────────────────────────────────[/]"
    )

    narrative: Optional[str] = None
    for comp in components_by_entity.get(stage_name, []):
        if comp.name == StageDescriptionComponent.__name__:
            narrative = StageDescriptionComponent(**comp.data).narrative
            break
    lines.append(f"  {narrative}" if narrative else "  [dim]（该场景暂无描述）[/]")

    lines.append("")
    lines.append("[bold yellow]── 场景内角色 ──────────────────────────────────────[/]")
    if not actor_names:
        lines.append("  [dim]（场景内暂无角色）[/]")
    for name in actor_names:
        appearance: Optional[str] = None
        for comp in components_by_entity.get(name, []):
            if comp.name == AppearanceComponent.__name__:
                appearance = AppearanceComponent(**comp.data).appearance
                break
        suffix = "  [dim](玩家)[/]" if name == player_actor else ""
        lines.append(f"  [bold cyan]{display_name(name)}[/]{suffix}")
        lines.append(
            f"    {appearance}"
            if appearance
            else "    [dim]（未持有 AppearanceComponent）[/]"
        )

    logger.info(
        f"build_stage_view_text: 成功 stage_name={stage_name} actors={len(actor_names)}"
    )
    return "\n".join(lines)
