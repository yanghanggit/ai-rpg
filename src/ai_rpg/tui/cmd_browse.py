"""实体浏览器命令：生成实体列表文本，供 HomeScreen 的 /browse（/b）调用。"""

from typing import List, Set

from loguru import logger

from .server_client import fetch_stages_state
from .utils import display_name


async def build_entity_browser_text(
    user_name: str, game_name: str, player_actor: str
) -> str:
    """获取并渲染实体列表，返回可写入正文区的富文本字符串。

    实体列表来自服务端场景状态（StagesStateResponse.mapping）：
    先列出全部场景（含场景内角色），再列出全部角色（去重、保持首次出现顺序），
    玩家角色会额外标注「(玩家)」。

    Args:
        user_name: 用户名
        game_name: 游戏名称
        player_actor: 玩家角色名，用于在角色列表中标注玩家

    Returns:
        可直接写入 RichLog 的富文本字符串

    Raises:
        服务端请求失败时向上抛出异常，由调用方决定如何展示错误。
    """
    logger.info(
        f"build_entity_browser_text: 请求实体列表 user_name={user_name} game_name={game_name}"
    )
    resp = await fetch_stages_state(user_name, game_name)

    stages = list(resp.mapping.keys())

    # 按首次出现顺序收集去重后的全部角色
    seen: Set[str] = set()
    actors: List[str] = []
    for actor_list in resp.mapping.values():
        for actor in actor_list:
            if actor not in seen:
                seen.add(actor)
                actors.append(actor)

    if not stages and not actors:
        return "[yellow]暂无实体数据。[/]"

    lines: List[str] = []
    lines.append("[bold cyan]── 实体浏览器 ──────────────────────────────────────[/]")

    lines.append(
        "[bold yellow]── 场景 ─────────────────────────────────────────────[/]"
    )
    idx = 1
    for name in stages:
        actors_in = resp.mapping.get(name, [])
        actors_str = (
            "、".join(display_name(a) for a in actors_in)
            if actors_in
            else "[dim]（空）[/]"
        )
        lines.append(
            f"  [bold]{idx}.[/] [bold cyan]{display_name(name)}[/]  → {actors_str}"
        )
        idx += 1

    lines.append(
        "[bold yellow]── 角色 ─────────────────────────────────────────────[/]"
    )
    for name in actors:
        if name == player_actor:
            lines.append(
                f"  [bold]{idx}.[/] [bold green]{display_name(name)}[/]  [dim](玩家)[/]"
            )
        else:
            lines.append(f"  [bold]{idx}.[/] [green]{display_name(name)}[/]")
        idx += 1

    logger.info(
        f"build_entity_browser_text: 成功，场景 {len(stages)} 个，角色 {len(actors)} 个"
    )
    return "\n".join(lines)
