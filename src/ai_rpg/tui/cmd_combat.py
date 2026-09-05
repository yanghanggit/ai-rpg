"""战斗房间命令：info / deck / inventory / inspect / start。"""

import json
from typing import List, Tuple

from loguru import logger

from ..models import (
    CharacterStatsComponent,
    CombatRoom,
    CombatState,
    DeathComponent,
    DeckComponent,
    HandComponent,
    InventoryComponent,
    compute_effective_stats,
)
from .combat_common import (
    find_component_data,
    find_stage_of_actor,
    resolve_current_energy,
    role_label,
)
from .server_client import (
    TaskFailedError,
    dungeon_combat_init,
    fetch_dungeon_room,
    fetch_entities_details,
    fetch_stages_state,
    watch_task_until_done,
)
from .utils import display_name, render_card, render_item


async def build_combat_info_text(
    user_name: str, game_name: str, player_actor: str
) -> str:
    """战斗宏观状态 + 场景角色有效属性，返回可写入正文区的富文本字符串。"""
    logger.info(f"build_combat_info_text: user_name={user_name} game_name={game_name}")
    try:
        room_resp = await fetch_dungeon_room(user_name, game_name)
        room = room_resp.room
        assert isinstance(room, CombatRoom), f"当前房间不是战斗房间：type={room.type}"
        combat = room.combat

        stages_resp = await fetch_stages_state(user_name, game_name)
        stage_name = find_stage_of_actor(stages_resp.mapping, player_actor)
        assert (
            stage_name is not None
        ), f"未能在场景映射中找到玩家角色所在场景：actor={player_actor}"
        participant_names = list(stages_resp.mapping[stage_name])
        entity_names = [stage_name, *participant_names]

        entities_resp = await fetch_entities_details(user_name, game_name, entity_names)
    except Exception as e:
        logger.error(f"build_combat_info_text: 加载失败 error={e}")
        return f"[bold red]❌ 加载战斗信息失败: {e}[/]"

    lines: List[str] = []
    lines.append("[bold yellow]── 战斗宏观状态 ─────────────────────────────────[/]")
    lines.append(f"  名称：   [bold]{combat.name}[/]")
    lines.append(f"  状态：   [cyan]{combat.state.name}[/]")
    lines.append(f"  结果：   [magenta]{combat.result.name}[/]")
    lines.append(f"  已撤退： {'[red]是[/]' if combat.retreated else '[green]否[/]'}")
    lines.append("")

    if combat.state == CombatState.INITIALIZATION:
        lines.append("[dim]下一步：输入 /start 开始战斗[/]")
        lines.append("")
    elif combat.state == CombatState.NONE:
        lines.append("[dim]战斗尚未初始化（NONE）[/]")
        lines.append("")

    lines.append(f"[bold yellow]── 场景：{display_name(stage_name)} ─────────────[/]")

    actor_entities = [e for e in entities_resp.entities if e.name != stage_name]
    if not actor_entities:
        lines.append("  [dim]（场景内暂无角色）[/]")
    else:
        for entity in actor_entities:
            stats_data = find_component_data(entity, CharacterStatsComponent.__name__)
            if stats_data is None:
                lines.append(
                    f"  [dim]{display_name(entity.name)}：缺少属性组件，跳过[/]"
                )
                continue

            base_stats = CharacterStatsComponent(**stats_data).stats
            hand_data = find_component_data(entity, HandComponent.__name__)
            hand_component = (
                HandComponent(**hand_data) if hand_data is not None else None
            )
            effective_stats = compute_effective_stats(base_stats, hand_component)
            current_energy = resolve_current_energy(entity, effective_stats)
            label = role_label(entity)
            is_dead = find_component_data(entity, DeathComponent.__name__) is not None
            death_mark = "  [bold red]（已战死）[/]" if is_dead else ""
            line = (
                f"  {label} [bold]{display_name(entity.name)}[/]{death_mark}  "
                f"HP:[yellow]{effective_stats.hp}/{effective_stats.max_hp}[/]  "
                f"攻:{effective_stats.attack}  防:{effective_stats.defense}  "
                f"能量:{current_energy}"
            )
            if hand_component is not None:
                line += f"  手牌:{len(hand_component.cards)}"
            lines.append(line)

    return "\n".join(lines)


async def build_deck_text(user_name: str, game_name: str, player_actor: str) -> str:
    """查阅战斗双方牌组（DeckComponent），返回可写入正文区的富文本字符串。"""
    logger.info(f"build_deck_text: user_name={user_name} game_name={game_name}")
    try:
        stages_resp = await fetch_stages_state(user_name, game_name)
        stage_name = find_stage_of_actor(stages_resp.mapping, player_actor)
        assert (
            stage_name is not None
        ), f"未能在场景映射中找到玩家角色所在场景：actor={player_actor}"
        participant_names = list(stages_resp.mapping[stage_name])
        if not participant_names:
            return "[yellow]场景内暂无参战者。[/]"
        resp = await fetch_entities_details(user_name, game_name, participant_names)
    except Exception as e:
        logger.error(f"build_deck_text: 加载失败 error={e}")
        return f"[bold red]❌ 加载牌组失败: {e}[/]"

    lines: List[str] = []
    lines.append(
        "[bold cyan]── 查阅牌组（双方） ──────────────────────────────────────[/]"
    )
    for entity in resp.entities:
        deck_data = find_component_data(entity, DeckComponent.__name__)
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


async def build_inventory_text(
    user_name: str, game_name: str, player_actor: str
) -> str:
    """查阅我方背包（玩家 InventoryComponent），返回可写入正文区的富文本字符串。"""
    logger.info(f"build_inventory_text: user_name={user_name} game_name={game_name}")
    try:
        resp = await fetch_entities_details(user_name, game_name, [player_actor])
    except Exception as e:
        logger.error(f"build_inventory_text: 加载失败 error={e}")
        return f"[bold red]❌ 加载背包失败: {e}[/]"

    entity = resp.entities[0] if resp.entities else None
    if entity is None:
        return "[yellow]未找到玩家角色。[/]"

    inventory_data = find_component_data(entity, InventoryComponent.__name__)
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


async def build_entity_inspect_text(
    user_name: str, game_name: str, entity_name: str
) -> str:
    """查阅单个实体的全部组件原始序列化数据，返回可写入正文区的富文本字符串。"""
    logger.info(f"build_entity_inspect_text: entity_name={entity_name}")
    try:
        resp = await fetch_entities_details(user_name, game_name, [entity_name])
    except Exception as e:
        logger.error(f"build_entity_inspect_text: 查询失败 error={e}")
        return f"[bold red]❌ 查询失败: {e}[/]"

    if not resp.entities:
        return f"[yellow]未找到实体：{entity_name}[/]"

    entity = resp.entities[0]
    lines: List[str] = []
    lines.append(f"[bold yellow]── 实体：{display_name(entity.name)} ──[/]")
    if not entity.components:
        lines.append("  [dim]（无组件）[/]")
    for comp in entity.components:
        data_str = json.dumps(comp.data, ensure_ascii=False, indent=2)
        lines.append(f"  [bold cyan][组件][/] [green]{comp.name}[/]")
        lines.append(f"[dim]{data_str}[/]")

    return "\n".join(lines)


async def start_combat(user_name: str, game_name: str) -> Tuple[bool, str]:
    """触发战斗初始化，返回 (是否成功, 展示文本)。成功后由调用方导航到 ONGOING 页。"""
    logger.info(f"start_combat: user_name={user_name} game_name={game_name}")
    try:
        resp = await dungeon_combat_init(user_name, game_name)
        record = await watch_task_until_done(resp.job_id)
    except TaskFailedError as e:
        logger.error(f"start_combat: 任务失败 error={e}")
        return False, f"[bold red]❌ 战斗初始化失败：{e}[/]"
    except Exception as e:
        logger.error(f"start_combat: 请求失败 error={e}")
        return False, f"[bold red]❌ 请求失败：{e}[/]"
    return True, f"[bold green]✅ 战斗初始化完成：{record.status}[/]"
