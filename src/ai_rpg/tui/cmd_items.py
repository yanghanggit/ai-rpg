"""道具管理命令：list / to-bag / to-storage，供 HomeScreen 的 items 系列命令调用。"""

from typing import List, Tuple

from loguru import logger
from pydantic import TypeAdapter

from ..models import InventoryComponent, StorageComponent
from ..models.items import AnyItem, CostumeItem
from .server_client import (
    fetch_entities_details,
    fetch_entities_group,
    home_item_move_to_inventory,
    home_item_move_to_storage,
)
from .utils import display_name, render_item

_ITEM_ADAPTER: TypeAdapter[AnyItem] = TypeAdapter(AnyItem)


async def _resolve_storage_entity(user_name: str, game_name: str) -> str:
    """解析全局储物箱实体名（WorldComponent + StorageComponent）。"""
    resp = await fetch_entities_group(
        user_name,
        game_name,
        all_of=["WorldComponent", "StorageComponent"],
        any_of=[],
        none_of=[],
    )
    assert len(resp.entities) == 1, "储物箱实体应恰好一个"
    return resp.entities[0].name


async def _fetch_all_items(
    user_name: str, game_name: str, player_actor: str, storage_entity: str
) -> List[Tuple[str, AnyItem]]:
    """获取背包与储物箱的道具列表，返回 [(位置, 道具), ...]。"""
    resp = await fetch_entities_details(
        user_name, game_name, [player_actor, storage_entity]
    )

    inventory_items: List[AnyItem] = []
    storage_items: List[AnyItem] = []
    for entity in resp.entities:
        for comp in entity.components:
            if comp.name == InventoryComponent.__name__:
                inventory_items = [
                    _ITEM_ADAPTER.validate_python(d) for d in comp.data.get("items", [])
                ]
            elif comp.name == StorageComponent.__name__:
                storage_items = [
                    _ITEM_ADAPTER.validate_python(d) for d in comp.data.get("items", [])
                ]

    return [("inventory", item) for item in inventory_items] + [
        ("storage", item) for item in storage_items
    ]


def _render_items_text(all_items: List[Tuple[str, AnyItem]]) -> str:
    """渲染道具列表文本（背包 / 储物箱 / 时装收藏只读）。"""
    inventory_items = [
        (i, item) for i, (loc, item) in enumerate(all_items) if loc == "inventory"
    ]
    storage_items = [
        (i, item)
        for i, (loc, item) in enumerate(all_items)
        if loc == "storage" and not isinstance(item, CostumeItem)
    ]
    costume_items = [
        (i, item)
        for i, (loc, item) in enumerate(all_items)
        if loc == "storage" and isinstance(item, CostumeItem)
    ]

    lines: List[str] = []
    lines.append("[bold yellow]── 道具列表 ──────────────────────────────────────[/]")

    lines.append("[bold green]  ▍随身背包[/]")
    if inventory_items:
        for global_idx, item in inventory_items:
            lines.append(
                f"  [bold green]{global_idx + 1}.[/] [cyan]【背包】[/] {render_item(item)}"
            )
    else:
        lines.append("  [dim]（空）[/]")

    lines.append("")
    lines.append("[bold blue]  ▍储物箱[/]")
    if storage_items:
        for global_idx, item in storage_items:
            lines.append(
                f"  [bold blue]{global_idx + 1}.[/] [dim]【储物】[/] {render_item(item)}"
            )
    else:
        lines.append("  [dim]（空）[/]")

    if costume_items:
        lines.append("")
        lines.append("[bold magenta]  ▍时装收藏[/] [dim]（只读，无法移动）[/]")
        for global_idx, item in costume_items:
            lines.append(
                f"  [bold magenta]{global_idx + 1}.[/] [magenta]【时装】[/] {render_item(item)}"
            )

    return "\n".join(lines)


async def build_items_list_text(
    user_name: str, game_name: str, player_actor: str
) -> str:
    """列出背包与储物箱道具，返回可写入正文区的富文本字符串。"""
    logger.info(
        f"build_items_list_text: 查询道具 user_name={user_name} game_name={game_name}"
    )
    try:
        storage_entity = await _resolve_storage_entity(user_name, game_name)
        all_items = await _fetch_all_items(
            user_name, game_name, player_actor, storage_entity
        )
        logger.info(f"build_items_list_text: 成功 共 {len(all_items)} 件道具")
        return _render_items_text(all_items)
    except Exception as e:
        logger.error(f"build_items_list_text: 失败 error={e}")
        return f"[bold red]❌ 读取道具列表失败: {e}[/]"


async def move_item_to_inventory(user_name: str, game_name: str, item_name: str) -> str:
    """将道具从储物箱移入背包，返回成功或失败文本。"""
    logger.info(
        f"move_item_to_inventory: 移入背包 user_name={user_name} item={item_name}"
    )
    try:
        await home_item_move_to_inventory(user_name, game_name, [item_name])
    except Exception as e:
        logger.error(f"move_item_to_inventory: 失败 item={item_name} error={e}")
        return f"[bold red]❌ 移动失败: {e}[/]"
    logger.info(f"move_item_to_inventory: 成功 item={item_name}")
    return f"[bold green]✅ {display_name(item_name)} 已移入随身背包[/]"


async def move_item_to_storage(user_name: str, game_name: str, item_name: str) -> str:
    """将道具从背包移入储物箱，返回成功或失败文本。"""
    logger.info(
        f"move_item_to_storage: 移入储物箱 user_name={user_name} item={item_name}"
    )
    try:
        await home_item_move_to_storage(user_name, game_name, [item_name])
    except Exception as e:
        logger.error(f"move_item_to_storage: 失败 item={item_name} error={e}")
        return f"[bold red]❌ 移动失败: {e}[/]"
    logger.info(f"move_item_to_storage: 成功 item={item_name}")
    return f"[bold green]✅ {display_name(item_name)} 已移入储物箱[/]"
