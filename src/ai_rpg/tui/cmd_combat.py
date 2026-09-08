"""战斗房间命令：info / deck / inventory / inspect / start。"""

import json
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from ..models import (
    CharacterStatsComponent,
    Combat,
    CombatRoom,
    CombatState,
    DeathComponent,
    DeckComponent,
    EntitySerialization,
    InventoryComponent,
    MonsterComponent,
    NPCComponent,
    PlayerComponent,
    compute_effective_stats,
)
from .app import GameClient
from .combat_data_access import (
    get_dungeon_room,
    get_entities_details,
    get_stages_state,
    is_mock_mode,
    resolve_identity,
)
from .mock_data import reset_mock_combat_rounds, set_mock_combat_state
from .server_client import (
    TaskFailedError,
    dungeon_combat_init,
    watch_task_until_done,
)
from .utils import display_name, render_card, render_item


###############################################################################################################################################
def find_component_data(
    entity: EntitySerialization, component_name: str
) -> Optional[Dict[str, Any]]:
    """在实体的组件序列化列表中按类名查找组件数据。"""
    for component in entity.components:
        if component.name == component_name:
            return component.data
    return None


###############################################################################################################################################
def find_stage_of_actor(
    mapping: Dict[str, List[str]], actor_name: str
) -> Optional[str]:
    """在场景映射中查找玩家控制角色所在的场景名。"""
    for stage_name, names in mapping.items():
        if actor_name in names:
            return stage_name
    return None


###############################################################################################################################################
def role_label(entity: EntitySerialization) -> str:
    """依据实体挂载的阵营标记组件返回展示标签。"""
    if find_component_data(entity, PlayerComponent.__name__) is not None:
        return "[bold green]👑玩家[/]"
    if find_component_data(entity, NPCComponent.__name__) is not None:
        return "[bold cyan]🤝队友[/]"
    if find_component_data(entity, MonsterComponent.__name__) is not None:
        return "[bold red]👹怪物[/]"
    return "[dim]？[/]"


###############################################################################################################################################
def classify_faction(entity: Optional[EntitySerialization]) -> str:
    """依据阵营标记组件返回 "party"（玩家 + 队友）/ "monster"（怪物）/ "unknown"。"""
    if entity is None:
        return "unknown"
    if find_component_data(entity, PlayerComponent.__name__) is not None:
        return "party"
    if find_component_data(entity, NPCComponent.__name__) is not None:
        return "party"
    if find_component_data(entity, MonsterComponent.__name__) is not None:
        return "monster"
    return "unknown"


###############################################################################################################################################
async def load_combat_overview(
    game_client: GameClient,
) -> Tuple[Combat, str, List[str], List[str]]:
    """加载并渲染「战斗宏观状态」与「场景角色有效属性（含死亡标记）」。

    返回 (combat, stage_name, macro_lines, actor_lines)。两个 /info 页面共用，
    保证宏观信息与参战角色属性展示逻辑一致。
    """
    _, _, player_actor = resolve_identity(game_client)

    room_resp = await get_dungeon_room(game_client)
    room = room_resp.room
    assert isinstance(room, CombatRoom), f"当前房间不是战斗房间：type={room.type}"
    combat = room.combat

    stages_resp = await get_stages_state(game_client)
    stage_name = find_stage_of_actor(stages_resp.mapping, player_actor)
    assert (
        stage_name is not None
    ), f"未能在场景映射中找到玩家角色所在场景：actor={player_actor}"
    participant_names = list(stages_resp.mapping[stage_name])
    entity_names = [stage_name, *participant_names]

    entities_resp = await get_entities_details(game_client, entity_names)

    macro_lines: List[str] = []
    macro_lines.append(
        "[bold yellow]── 战斗宏观状态 ─────────────────────────────────[/]"
    )
    macro_lines.append(f"  名称：   [bold]{combat.name}[/]")
    macro_lines.append(f"  状态：   [cyan]{combat.state.name}[/]")
    macro_lines.append(f"  结果：   [magenta]{combat.result.name}[/]")
    macro_lines.append(
        f"  已撤退： {'[red]是[/]' if combat.retreated else '[green]否[/]'}"
    )

    actor_lines: List[str] = []
    actor_lines.append(
        f"[bold yellow]── 场景：{display_name(stage_name)} ─────────────[/]"
    )

    actor_entities = [e for e in entities_resp.entities if e.name != stage_name]
    if not actor_entities:
        actor_lines.append("  [dim]（场景内暂无角色）[/]")
    else:
        for entity in actor_entities:
            stats_data = find_component_data(entity, CharacterStatsComponent.__name__)
            if stats_data is None:
                actor_lines.append(
                    f"  [dim]{display_name(entity.name)}：缺少属性组件，跳过[/]"
                )
                continue

            base_stats = CharacterStatsComponent(**stats_data).stats
            effective_stats = compute_effective_stats(base_stats)
            label = role_label(entity)
            is_dead = find_component_data(entity, DeathComponent.__name__) is not None
            death_mark = "  [bold red]（已战死）[/]" if is_dead else ""
            line = (
                f"  {label} [bold]{display_name(entity.name)}[/]{death_mark}  "
                f"HP:[yellow]{effective_stats.hp}/{effective_stats.max_hp}[/]  "
                f"ATK:{effective_stats.attack}  DEF:{effective_stats.defense}"
            )
            actor_lines.append(line)

    return combat, stage_name, macro_lines, actor_lines


async def build_combat_info_text(game_client: GameClient) -> str:
    """战斗宏观状态 + 场景角色有效属性，返回可写入正文区的富文本字符串。"""
    logger.info(f"build_combat_info_text: mock={is_mock_mode(game_client)}")
    try:
        combat, _, macro_lines, actor_lines = await load_combat_overview(game_client)
    except Exception as e:
        logger.error(f"build_combat_info_text: 加载失败 error={e}")
        return f"[bold red]❌ 加载战斗信息失败: {e}[/]"

    lines: List[str] = [*macro_lines]
    if combat.state == CombatState.INITIALIZATION:
        lines.append("")
        lines.append("[dim]下一步：输入 /begin 开始执行回合[/]")
    elif combat.state == CombatState.NONE:
        lines.append("")
        lines.append("[dim]战斗尚未初始化（NONE）[/]")
    lines.append("")
    lines.extend(actor_lines)
    return "\n".join(lines)


async def build_deck_text(game_client: GameClient) -> str:
    """查阅战斗双方牌组（DeckComponent），返回可写入正文区的富文本字符串。"""
    _, _, player_actor = resolve_identity(game_client)
    logger.info(
        f"build_deck_text: mock={is_mock_mode(game_client)} actor={player_actor}"
    )
    try:
        stages_resp = await get_stages_state(game_client)
        stage_name = find_stage_of_actor(stages_resp.mapping, player_actor)
        assert (
            stage_name is not None
        ), f"未能在场景映射中找到玩家角色所在场景：actor={player_actor}"
        participant_names = list(stages_resp.mapping[stage_name])
        if not participant_names:
            return "[yellow]场景内暂无参战者。[/]"
        resp = await get_entities_details(game_client, participant_names)
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


async def build_inventory_text(game_client: GameClient) -> str:
    """查阅我方背包（玩家 InventoryComponent），返回可写入正文区的富文本字符串。"""
    _, _, player_actor = resolve_identity(game_client)
    logger.info(
        f"build_inventory_text: mock={is_mock_mode(game_client)} actor={player_actor}"
    )
    try:
        resp = await get_entities_details(game_client, [player_actor])
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


async def build_entity_inspect_text(game_client: GameClient, entity_name: str) -> str:
    """查阅单个实体的全部组件原始序列化数据，返回可写入正文区的富文本字符串。"""
    logger.info(
        f"build_entity_inspect_text: mock={is_mock_mode(game_client)} "
        f"entity_name={entity_name}"
    )
    try:
        resp = await get_entities_details(game_client, [entity_name])
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


async def start_combat(game_client: GameClient) -> Tuple[bool, str]:
    """触发战斗初始化，返回 (是否成功, 展示文本)。成功后由调用方导航到 ONGOING 页。"""
    if is_mock_mode(game_client):
        logger.info("start_combat: mock 模式，直接切换战斗状态为 ONGOING")
        set_mock_combat_state(CombatState.ONGOING)
        reset_mock_combat_rounds()
        return True, "[bold green]✅ 战斗初始化完成（mock：状态已置为 ONGOING）[/]"

    user_name, game_name, _ = resolve_identity(game_client)
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
