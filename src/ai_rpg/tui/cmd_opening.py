"""开场房间命令：info / deck / card-pool / inventory / init / generate-pool / pick / next。"""

from typing import List, Optional, Tuple

from loguru import logger

from ..models import (
    CardPoolComponent,
    DeckComponent,
    InventoryComponent,
    OpeningRoom,
    StageDescriptionComponent,
)
from .server_client import (
    TaskFailedError,
    dungeon_advance_stage,
    dungeon_opening_generate_card_pool,
    dungeon_opening_init,
    dungeon_opening_pick_card_from_pool,
    fetch_dungeon_room,
    fetch_dungeon_state,
    fetch_entities_details,
    fetch_stages_state,
    watch_task_until_done,
)
from .utils import display_name, render_card, render_item


async def _fetch_party_names(
    user_name: str, game_name: str, player_actor: str
) -> List[str]:
    """返回玩家所在场景内的全部参与者（含玩家与队友）。"""
    stages_resp = await fetch_stages_state(user_name, game_name)
    for actors in stages_resp.mapping.values():
        if player_actor in actors:
            return list(actors)
    return []


async def build_opening_info_text(
    user_name: str, game_name: str, player_actor: str
) -> str:
    """开场房间状态总览：初始化状态 + 卡池状态 + 场景描述。"""
    logger.info(f"build_opening_info_text: user_name={user_name} game_name={game_name}")
    try:
        room_resp = await fetch_dungeon_room(user_name, game_name)
        room = room_resp.room

        stages_resp = await fetch_stages_state(user_name, game_name)
        stage_name: Optional[str] = None
        party_names: List[str] = []
        for stage, actors in stages_resp.mapping.items():
            if player_actor in actors:
                stage_name = stage
                party_names = list(actors)
                break

        entity_names = ([stage_name] if stage_name else []) + party_names
        entities_resp = await fetch_entities_details(user_name, game_name, entity_names)
    except Exception as e:
        logger.error(f"build_opening_info_text: 查询失败 error={e}")
        return f"[bold red]❌ 查询房间状态失败: {e}[/]"

    lines: List[str] = []
    lines.append("[bold cyan]── 开场房间状态 ──────────────────────────────────────[/]")

    if isinstance(room, OpeningRoom):
        init_tag = (
            "[bold green]✅ 已初始化[/]" if room.initialized else "[yellow]未初始化[/]"
        )
        lines.append(f"  初始化（叙事 + 牌库）：{init_tag}")

        pool_ready = any(
            any(c.name == CardPoolComponent.__name__ for c in e.components)
            for e in entities_resp.entities
        )
        pool_tag = "[bold green]✅ 已生成[/]" if pool_ready else "[yellow]未生成[/]"
        lines.append(f"  卡池：{pool_tag}")
    else:
        lines.append(f"  [red]当前房间类型：{room.type}（非开场房间）[/]")

    if stage_name is not None:
        narrative: Optional[str] = None
        for entity in entities_resp.entities:
            if entity.name == stage_name:
                for comp in entity.components:
                    if comp.name == StageDescriptionComponent.__name__:
                        narrative = StageDescriptionComponent(**comp.data).narrative
                        break
        lines.append("")
        lines.append(
            f"[bold yellow]── 场景：{display_name(stage_name)} ─────────────────────────────[/]"
        )
        lines.append(
            f"  {narrative}" if narrative else "  [dim]（场景环境描述未生成）[/]"
        )

    return "\n".join(lines)


async def build_deck_text(user_name: str, game_name: str, player_actor: str) -> str:
    """查阅我方牌组，返回可写入正文区的富文本字符串。"""
    logger.info(f"build_deck_text: user_name={user_name} game_name={game_name}")
    try:
        party_names = await _fetch_party_names(user_name, game_name, player_actor)
        if not party_names:
            return "[yellow]无法确定队伍成员。[/]"
        resp = await fetch_entities_details(user_name, game_name, party_names)
    except Exception as e:
        logger.error(f"build_deck_text: 加载失败 error={e}")
        return f"[bold red]❌ 加载牌组失败: {e}[/]"

    lines: List[str] = []
    lines.append(
        "[bold cyan]── 查阅牌组（我方） ──────────────────────────────────────[/]"
    )
    for entity in resp.entities:
        deck_data = None
        for comp in entity.components:
            if comp.name == DeckComponent.__name__:
                deck_data = comp.data
                break
        lines.append(f"[bold yellow]── {display_name(entity.name)} ──[/]")
        if deck_data is None:
            lines.append("  [dim]（无牌组组件）[/]")
        else:
            deck = DeckComponent(**deck_data)
            if not deck.cards:
                lines.append("  [dim]（牌组为空）[/]")
            else:
                lines.append(f"  共 [bold]{len(deck.cards)}[/] 张：")
                for card in deck.cards:
                    lines.append(render_card(card))
        lines.append("")

    return "\n".join(lines)


async def build_card_pool_text(
    user_name: str, game_name: str, player_actor: str
) -> str:
    """查阅我方卡池，返回可写入正文区的富文本字符串。"""
    logger.info(f"build_card_pool_text: user_name={user_name} game_name={game_name}")
    try:
        party_names = await _fetch_party_names(user_name, game_name, player_actor)
        if not party_names:
            return "[yellow]无法确定队伍成员。[/]"
        resp = await fetch_entities_details(user_name, game_name, party_names)
    except Exception as e:
        logger.error(f"build_card_pool_text: 加载失败 error={e}")
        return f"[bold red]❌ 加载卡池失败: {e}[/]"

    lines: List[str] = []
    lines.append(
        "[bold cyan]── 查阅卡池（我方） ──────────────────────────────────────[/]"
    )
    for entity in resp.entities:
        pool_data = None
        for comp in entity.components:
            if comp.name == CardPoolComponent.__name__:
                pool_data = comp.data
                break
        lines.append(f"[bold yellow]── {display_name(entity.name)} ──[/]")
        if pool_data is None:
            lines.append("  [dim]（无卡池组件，请先执行 /generate-pool）[/]")
        else:
            pool = CardPoolComponent(**pool_data)
            if not pool.cards:
                lines.append("  [dim]（卡池为空）[/]")
            else:
                lines.append(f"  候选卡 [bold]{len(pool.cards)}[/] 张：")
                for card in pool.cards:
                    lines.append(render_card(card))
        lines.append("")

    return "\n".join(lines)


async def build_inventory_text(
    user_name: str, game_name: str, player_actor: str
) -> str:
    """查阅我方背包，返回可写入正文区的富文本字符串。"""
    logger.info(f"build_inventory_text: user_name={user_name} game_name={game_name}")
    try:
        resp = await fetch_entities_details(user_name, game_name, [player_actor])
    except Exception as e:
        logger.error(f"build_inventory_text: 加载失败 error={e}")
        return f"[bold red]❌ 加载背包失败: {e}[/]"

    entity = resp.entities[0] if resp.entities else None
    if entity is None:
        return "[yellow]未找到玩家角色。[/]"

    inventory_data = None
    for comp in entity.components:
        if comp.name == InventoryComponent.__name__:
            inventory_data = comp.data
            break

    lines: List[str] = []
    lines.append(f"[bold yellow]── {display_name(entity.name)} 的背包 ──[/]")
    if inventory_data is None:
        lines.append("  [dim]（无背包组件）[/]")
    else:
        inventory = InventoryComponent(**inventory_data)
        if not inventory.items:
            lines.append("  [dim]（背包为空）[/]")
        else:
            lines.append(f"  共 [bold]{len(inventory.items)}[/] 件道具：")
            for item in inventory.items:
                lines.append(render_item(item))

    return "\n".join(lines)


async def init_opening(user_name: str, game_name: str) -> str:
    """初始化开场房间（叙事 + 牌库），返回成功或失败文本。"""
    logger.info(f"init_opening: user_name={user_name} game_name={game_name}")
    try:
        resp = await dungeon_opening_init(user_name, game_name)
        await watch_task_until_done(resp.job_id)
    except TaskFailedError as e:
        logger.error(f"init_opening: 任务失败 error={e}")
        return f"[bold red]❌ 开场房间初始化失败: {e}[/]"
    except Exception as e:
        logger.error(f"init_opening: 请求失败 error={e}")
        return f"[bold red]❌ 请求失败: {e}[/]"
    return "[bold green]✅ 开场房间初始化完成（叙事 + 牌库）。[/]"


async def generate_card_pool(user_name: str, game_name: str) -> str:
    """生成卡池，返回成功或失败文本。"""
    logger.info(f"generate_card_pool: user_name={user_name} game_name={game_name}")
    try:
        resp = await dungeon_opening_generate_card_pool(user_name, game_name)
        await watch_task_until_done(resp.job_id)
    except TaskFailedError as e:
        logger.error(f"generate_card_pool: 任务失败 error={e}")
        return f"[bold red]❌ 卡池生成失败: {e}[/]"
    except Exception as e:
        logger.error(f"generate_card_pool: 请求失败 error={e}")
        return f"[bold red]❌ 请求失败: {e}[/]"
    return "[bold green]✅ 卡池生成完成。[/]"


async def pick_card(
    user_name: str, game_name: str, actor_name: str, card_name: str
) -> str:
    """从指定角色的卡池挑一张卡加入其牌库，返回成功或失败文本。"""
    logger.info(f"pick_card: user_name={user_name} actor={actor_name} card={card_name}")
    try:
        resp = await dungeon_opening_pick_card_from_pool(
            user_name, game_name, actor_name, card_name
        )
        await watch_task_until_done(resp.job_id)
    except TaskFailedError as e:
        logger.error(f"pick_card: 任务失败 error={e}")
        return f"[bold red]❌ 挑卡失败: {e}[/]"
    except Exception as e:
        logger.error(f"pick_card: 请求失败 error={e}")
        return f"[bold red]❌ 请求失败: {e}[/]"
    return (
        f"[bold green]✅ 已从 {display_name(actor_name)} 的卡池挑选"
        f"「{card_name}」加入其牌库。[/]"
    )


async def advance_stage(user_name: str, game_name: str) -> Tuple[bool, str]:
    """进入下一关，返回 (是否成功, 展示文本)。成功后由调用方导航到准备页。"""
    logger.info(f"advance_stage: user_name={user_name} game_name={game_name}")
    try:
        dungeon_resp = await fetch_dungeon_state(user_name, game_name)
        dungeon = dungeon_resp.dungeon
        next_index = dungeon.current_room_index + 1
        if next_index >= len(dungeon.rooms):
            return False, "[bold red]❌ 已是最后一关，无法继续推进。[/]"

        resp = await dungeon_advance_stage(user_name, game_name)
        return True, f"[bold green]✅ {resp.message}[/]"
    except Exception as e:
        logger.error(f"advance_stage: 推进失败 error={e}")
        return False, f"[bold red]❌ 进入下一关失败: {e}[/]"
