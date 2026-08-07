"""
副本推进模块 —— 推进到副本下一关卡

advance_dungeon 是推进副本的唯一入口。
"""

from typing import Set
from loguru import logger
from ..game.dbg_game import DBGGame
from ..game.dbg_combat_processor import (
    set_character_hp,
    clear_combat_state,
)
from ..game.rpg_stage_transition import stage_transition
from ..models import (
    Dungeon,
    DungeonComponent,
    Combat,
    HumanMessage,
    PartyMemberComponent,
    DeathComponent,
    CombatRoom,
    CombatState,
)
from ..entitas import Matcher, Entity


###################################################################################################################################################################
def _generate_advance_message(
    dungeon_name: str,
    dungeon_stage_name: str,
) -> str:
    """生成关卡推进提示消息"""
    return f"""# 副本：{dungeon_name}，进入下一关卡场景：{dungeon_stage_name}"""


###################################################################################################################################################################
def _advance_to_next_stage(
    dbg_game: DBGGame, dungeon: Dungeon, party_member_entities: Set[Entity]
) -> bool:
    """
    进入副本下一关卡并初始化战斗环境
    """
    if len(party_member_entities) == 0:
        logger.error("没有远征队成员不能推进关卡!")
        return False

    current_room = dungeon.current_room
    if current_room is None:
        logger.error("当前副本房间不存在，无法推进关卡")
        return False

    assert isinstance(current_room, CombatRoom), "当前副本房间必须是战斗房间"
    stage_model = current_room.stage
    assert stage_model is not None, f"{dungeon.name} 副本关卡数据异常！"

    stage_entity = dbg_game.get_stage_entity(stage_model.name)
    assert stage_entity is not None, f"{stage_model.name} 没有对应的stage实体！"

    assert stage_entity.has(
        DungeonComponent
    ), f"{stage_model.name} 没有DungeonComponent组件！"

    trans_message = _generate_advance_message(
        dungeon.name,
        stage_entity.name,
    )

    for party_member in party_member_entities:
        dbg_game.add_human_message(
            party_member,
            HumanMessage(
                content=trans_message,
                dungeon_lifecycle_stage_advance=f"{dungeon.name}:{stage_entity.name}",
            ),
        )

        if party_member.has(DeathComponent):
            logger.info(f"移除死亡组件: {party_member.name}")
            party_member.remove(DeathComponent)
            revived_stats = set_character_hp(party_member, 1)
            logger.info(
                f"恢复生命值: {party_member.name} 生命值 = {revived_stats.hp}/{revived_stats.max_hp}"
            )

    stage_transition(dbg_game, party_member_entities, stage_entity)

    combat = Combat(name=stage_entity.name)
    combat.state = CombatState.INITIALIZATION
    current_room.combat = combat

    return True


###################################################################################################################################################################
def advance_dungeon(dbg_game: DBGGame, dungeon: Dungeon) -> None:
    """
    推进到副本的下一个关卡
    """

    if not dbg_game.current_combat_room.combat.is_post_combat:
        logger.error("当前不处于战斗后状态，无法推进副本关卡")
        return

    if dbg_game.current_combat_room.combat.is_lost:
        logger.info("英雄失败，应该返回营地！！！！")
        return

    if not dbg_game.current_combat_room.combat.is_won:
        assert False, "不可能出现的情况！"

    # 1. 推进副本索引到下一关
    next_room_index = dungeon.current_room_index + 1
    next_room = dungeon.get_room(next_room_index)
    if next_room is None:
        logger.error("副本前进失败，没有更多房间")
        return

    assert isinstance(next_room, CombatRoom), "下一房间必须是战斗房间"
    dungeon.current_room_index = next_room_index

    # 2. 获取所有远征队成员
    party_member_entities = dbg_game.get_group(
        Matcher(all_of=[PartyMemberComponent])
    ).entities.copy()
    assert len(party_member_entities) > 0, "没有找到远征队成员"

    # 3. 进入下一关卡
    enter = _advance_to_next_stage(dbg_game, dungeon, party_member_entities)
    assert enter, "进入下一关卡失败！"

    # 清除上一场战斗的临时状态
    clear_combat_state(dbg_game)
