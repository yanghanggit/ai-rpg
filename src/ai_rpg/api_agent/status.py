"""服务器世界状态观测。

把原先散落在各 TUI Screen 里的「取数 + 判读」逻辑收拢成**一次**结构化快照，
供 AI 代理（``ai_rpg/cli/agent_api.py``）调用一次 ``status`` 即可掌握当前局面。

设计要点：
- 只读、无副作用；服务端内存才是唯一真相，本模块不缓存任何状态。
- 输出为纯 JSON 可序列化的 dict，字段尽量对齐 ``ai_rpg.models``。
- 玩家角色名（player_actor）可通过 PlayerComponent 反查，因此调用方无需预先登录态。
"""

from typing import Any, Dict, List, Optional

from ..models import (
    AppearanceComponent,
    CharacterStatsComponent,
    Combat,
    CombatRoom,
    DeathComponent,
    EnvironmentComponent,
    HandComponent,
    InventoryComponent,
    MonsterComponent,
    NPCComponent,
    OpeningRoom,
    PartyRosterComponent,
    PlayerComponent,
    RoundStatsComponent,
    SpoilsComponent,
    StorageComponent,
    WorldComponent,
    compute_effective_stats,
    compute_hand_block,
)
from .server_client import (
    fetch_dungeon_state,
    fetch_entities_details,
    fetch_entities_group,
    fetch_session_messages,
    fetch_stages_state,
)


########################################################################################################################
def component_data(entity: Any, component_name: str) -> Optional[Dict[str, Any]]:
    """在实体序列化数据中按组件类名取原始 dict。"""
    for component in entity.components:
        if component.name == component_name:
            return dict(component.data)
    return None


########################################################################################################################
def find_stage_of_actor(
    actors_by_stage: Dict[str, List[str]], actor_name: str
) -> Optional[str]:
    """在场景映射中查找某角色所在的场景名。"""
    for stage_name, names in actors_by_stage.items():
        if actor_name in names:
            return stage_name
    return None


########################################################################################################################
def role_of(entity: Any) -> str:
    """依据阵营标记组件返回 "player" / "npc" / "monster" / "unknown"。"""
    if component_data(entity, PlayerComponent.__name__) is not None:
        return "player"
    if component_data(entity, NPCComponent.__name__) is not None:
        return "npc"
    if component_data(entity, MonsterComponent.__name__) is not None:
        return "monster"
    return "unknown"


########################################################################################################################
async def resolve_player_actor(
    user_name: str, game_name: str, actor: Optional[str] = None
) -> str:
    """解析玩家角色名。显式传入时直接使用，否则按 PlayerComponent 反查。"""
    if actor:
        return actor
    resp = await fetch_entities_group(
        user_name,
        game_name,
        all_of=[PlayerComponent.__name__],
        any_of=[],
        none_of=[],
    )
    if not resp.entities:
        raise RuntimeError(
            "未找到玩家实体（PlayerComponent）；请确认已 new-game，或用 --actor 显式指定"
        )
    return str(resp.entities[0].name)


########################################################################################################################
def _entity_summary(entity: Any) -> Dict[str, Any]:
    """把单个实体压缩成代理决策所需的摘要（角色/生死/属性/能量/格挡/手牌）。"""
    summary: Dict[str, Any] = {"name": entity.name, "role": role_of(entity)}
    summary["dead"] = component_data(entity, DeathComponent.__name__) is not None

    stats_data = component_data(entity, CharacterStatsComponent.__name__)
    if stats_data is not None:
        stats = compute_effective_stats(CharacterStatsComponent(**stats_data).stats)
        summary["hp"] = stats.hp
        summary["max_hp"] = stats.max_hp
        summary["attack"] = stats.attack
        summary["defense"] = stats.defense

    round_stats_data = component_data(entity, RoundStatsComponent.__name__)
    if round_stats_data is not None:
        summary["energy"] = RoundStatsComponent(**round_stats_data).energy

    hand_data = component_data(entity, HandComponent.__name__)
    hand = HandComponent(**hand_data) if hand_data is not None else None
    summary["block"] = compute_hand_block(hand)
    summary["hand"] = (
        [card.model_dump(mode="json") for card in hand.cards] if hand else []
    )

    appearance = component_data(entity, AppearanceComponent.__name__)
    if appearance is not None:
        summary["appearance"] = AppearanceComponent(**appearance).appearance

    return summary


########################################################################################################################
def _round_summary(combat: Combat) -> Optional[Dict[str, Any]]:
    """最近一回合的回合内状态与日志。"""
    latest = combat.latest_round
    if latest is None:
        return None
    return {
        "draw_completed": latest.draw_completed,
        "is_completed": latest.is_completed,
        "current_actor": latest.current_actor,
        "action_order": list(latest.action_order),
        "completed_actors": list(latest.completed_actors),
        "consumable_use_count": latest.consumable_use_count,
        "gear_equip_count": latest.gear_equip_count,
        "cards_log": list(latest.cards_log),
        "cards_narrative": list(latest.cards_narrative),
        "consumable_log": list(latest.consumable_log),
        "consumable_narrative": list(latest.consumable_narrative),
        "gear_log": list(latest.gear_log),
        "gear_narrative": list(latest.gear_narrative),
        "artifact_log": list(latest.artifact_log),
        "artifact_narrative": list(latest.artifact_narrative),
    }


########################################################################################################################
async def _fetch_storage_items(user_name: str, game_name: str) -> List[Dict[str, Any]]:
    """读取全局储物箱（WorldComponent + StorageComponent）内的道具列表。"""
    resp = await fetch_entities_group(
        user_name,
        game_name,
        all_of=[WorldComponent.__name__, StorageComponent.__name__],
        any_of=[],
        none_of=[],
    )
    if not resp.entities:
        return []
    for component in resp.entities[0].components:
        if component.name == StorageComponent.__name__:
            storage = StorageComponent(**component.data)
            return [item.model_dump(mode="json") for item in storage.items]
    return []


########################################################################################################################
def _player_extras(player_entity: Any) -> Dict[str, Any]:
    """从玩家实体取队伍名单与随身背包。"""
    roster_data = component_data(player_entity, PartyRosterComponent.__name__)
    roster = list(PartyRosterComponent(**roster_data).members) if roster_data else []
    inventory_data = component_data(player_entity, InventoryComponent.__name__)
    inventory = (
        [
            item.model_dump(mode="json")
            for item in InventoryComponent(**inventory_data).items
        ]
        if inventory_data
        else []
    )
    return {"roster": roster, "inventory": inventory}


########################################################################################################################
def _opening_info(room: OpeningRoom, party_entities: List[Any]) -> Dict[str, Any]:
    """开场房间：初始化标记 + 奖励候选/已领取队列。"""
    candidate_cards: List[Dict[str, Any]] = []
    claimed_cards: List[Dict[str, Any]] = []
    by_actor: List[Dict[str, Any]] = []
    for entity in party_entities:
        spoils_data = component_data(entity, SpoilsComponent.__name__)
        if spoils_data is None:
            continue
        spoils = SpoilsComponent(**spoils_data)
        candidates = [card.model_dump(mode="json") for card in spoils.candidate_cards]
        claimed = [card.model_dump(mode="json") for card in spoils.claimed_cards]
        candidate_cards.extend(candidates)
        claimed_cards.extend(claimed)
        by_actor.append(
            {
                "actor": entity.name,
                "candidate_cards": candidates,
                "claimed_cards": claimed,
            }
        )
    return {
        "initialized": room.initialized,
        "spoils_generated": len(by_actor) > 0,
        "candidate_cards": candidate_cards,
        "claimed_cards": claimed_cards,
        "by_actor": by_actor,
    }


########################################################################################################################
def _combat_info(combat: Combat) -> Dict[str, Any]:
    return {
        "name": combat.name,
        "state": combat.state.name,
        "result": combat.result.name,
        "retreated": combat.retreated,
        "round_count": len(combat.rounds),
        "round": _round_summary(combat),
    }


########################################################################################################################
async def build_status(
    user_name: str,
    game_name: str,
    actor: Optional[str] = None,
    messages_since: int = 0,
) -> Dict[str, Any]:
    """构建当前世界状态快照。

    Args:
        user_name: 用户名
        game_name: 游戏名
        actor: 玩家角色名；None 时按 PlayerComponent 反查
        messages_since: 拉取会话消息的起始 sequence_id（0 表示全量）
    """
    player_actor = await resolve_player_actor(user_name, game_name, actor)

    stages_resp = await fetch_stages_state(user_name, game_name)
    stage_name = find_stage_of_actor(stages_resp.actors_by_stage, player_actor)
    actor_names = (
        list(stages_resp.actors_by_stage.get(stage_name, [])) if stage_name else []
    )
    entity_names = ([stage_name] if stage_name else []) + actor_names

    details_resp = await fetch_entities_details(user_name, game_name, entity_names)
    entities = list(details_resp.entities)
    entities_by_name = {entity.name: entity for entity in entities}

    # 场景描述
    stage_block: Dict[str, Any] = {"name": stage_name, "actors": actor_names}
    if stage_name is not None:
        stage_entity = entities_by_name.get(stage_name)
        narrative = None
        if stage_entity is not None:
            env_data = component_data(stage_entity, EnvironmentComponent.__name__)
            if env_data is not None:
                narrative = EnvironmentComponent(**env_data).narrative
        stage_block["narrative"] = narrative

    status: Dict[str, Any] = {
        "user_name": user_name,
        "game_name": game_name,
        "player_actor": player_actor,
        "stage": stage_block,
        "entities": [_entity_summary(entity) for entity in entities],
    }

    # 副本 / 战斗
    dungeon_resp = await fetch_dungeon_state(user_name, game_name)
    dungeon = dungeon_resp.dungeon
    room = dungeon.current_room
    mode = "dungeon" if room is not None else "home"
    status["mode"] = mode
    status["dungeon"] = {
        "name": dungeon.name,
        "current_room_index": dungeon.current_room_index,
        "room_count": len(dungeon.rooms),
        "setup_entities": dungeon.setup_entities,
        "room_type": room.type if room is not None else None,
        "archive_summary": dungeon.archive_summary,
    }

    party_entities = [
        entities_by_name[name] for name in actor_names if name in entities_by_name
    ]

    if isinstance(room, CombatRoom):
        status["combat"] = _combat_info(room.combat)
    elif isinstance(room, OpeningRoom):
        status["dungeon"]["opening"] = _opening_info(room, party_entities)

    # 家园附加信息（仅在非副本态查询储物箱，避免多余往返）
    player_entity = entities_by_name.get(player_actor)
    if player_entity is not None:
        status["player"] = _player_extras(player_entity)
    if mode == "home":
        status["home"] = {
            "storage": await _fetch_storage_items(user_name, game_name),
        }

    # 会话消息
    messages_resp = await fetch_session_messages(user_name, game_name, messages_since)
    status["session_messages"] = [
        message.model_dump(mode="json") for message in messages_resp.session_messages
    ]

    return status
