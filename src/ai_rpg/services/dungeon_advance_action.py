"""
副本推进模块 —— 推进到副本下一关卡

advance_dungeon 是推进副本的唯一入口。
"""

from typing import Tuple
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
from ..entitas import Matcher


###################################################################################################################################################################
def advance_dungeon(dbg_game: DBGGame, dungeon: Dungeon) -> Tuple[bool, str]:
    """
    推进到副本的下一个关卡。

    流程分为两个阶段：
      1) 检查阶段 —— 仅读取、验证，不修改任何状态，允许早期返回。
      2) 执行阶段 —— 一旦进入就不可能中断，所有操作均为断言或动作。
    """

    # =========================================================================
    # 阶段 1：检查（零状态变更，允许 return）
    # =========================================================================

    current_room = dungeon.rooms[dungeon.current_room_index]
    next_room_index = dungeon.current_room_index + 1

    # 下一房间必须存在
    if next_room_index >= len(dungeon.rooms):
        logger.error("副本前进失败，没有更多房间")
        return False, "副本已全部通关"

    next_room = dungeon.rooms[next_room_index]

    # 下一房间的关卡实体必须存在
    next_stage_entity = dbg_game.get_stage_entity(next_room.stage.name)
    assert (
        next_stage_entity is not None
    ), f"{next_room.stage.name} 没有对应的 stage 实体！"
    assert next_stage_entity.has(
        DungeonComponent
    ), f"{next_room.stage.name} 没有 DungeonComponent 组件！"

    # 确保存在远征队成员
    party_member_entities = dbg_game.get_group(
        Matcher(all_of=[PartyMemberComponent])
    ).entities.copy()
    assert len(party_member_entities) > 0, "没有找到远征队成员"

    # 当前房间若是战斗房间，必须处于战斗后且已胜利
    if isinstance(current_room, CombatRoom):
        if not current_room.combat.is_post_combat:
            logger.error("当前不处于战斗后状态，无法推进副本关卡")
            return False, "战斗未结束，无法推进"

        if current_room.combat.is_lost:
            logger.info("英雄失败，应该返回营地")
            return False, "战斗失败，无法推进"

        assert current_room.combat.is_won, "不可能出现的情况！"

    # =========================================================================
    # 阶段 2：执行（不可中断，不回退）
    # =========================================================================

    # 推进索引
    dungeon.current_room_index = next_room_index

    # 生成并发送传送提示消息
    trans_message = (
        f"# 副本：{dungeon.name}，进入下一关卡场景：{next_stage_entity.name}\n"
        f"（关于「副本」及进出副本的具体设定，见你的「游戏设定」与「全局规则」。）"
    )
    for party_member in party_member_entities:
        dbg_game.add_human_message(
            party_member,
            HumanMessage(
                content=trans_message,
                dungeon_lifecycle_stage_advance=f"{dungeon.name}:{next_stage_entity.name}",
            ),
        )

        # 战斗中可能死亡，推进关卡时复活并恢复 1 点生命值
        if party_member.has(DeathComponent):
            logger.info(f"移除死亡组件: {party_member.name}")
            party_member.remove(DeathComponent)
            revived_stats = set_character_hp(party_member, 1)
            logger.info(
                f"恢复生命值: {party_member.name} 生命值 = {revived_stats.hp}/{revived_stats.max_hp}"
            )

    # 执行场景传送
    stage_transition(dbg_game, party_member_entities, next_stage_entity)

    # 离开战斗房间时清除残留战斗状态
    if isinstance(current_room, CombatRoom):
        clear_combat_state(dbg_game)

    # 进入战斗房间时创建战斗实例并初始化
    if isinstance(next_room, CombatRoom):
        combat = Combat(name=next_stage_entity.name)
        combat.state = CombatState.INITIALIZATION
        next_room.combat = combat

    logger.info(f"advance_dungeon 完成: {dungeon.name}，进入第 {next_room_index} 关")
    return True, f"已前进到第 {next_room_index} 关"
