"""
副本退出模块 —— 退出副本并传送角色回家园

exit_dungeon 是退出副本的唯一入口。
"""

from typing import Tuple
from loguru import logger
from ..game.dbg_game import DBGGame
from ..game.dbg_combat_processor import (
    compute_character_stats,
    set_character_hp,
    clear_combat_state,
)
from ..game.rpg_stage_transition import stage_transition
from ..models import (
    Dungeon,
    HumanMessage,
    PartyMemberComponent,
    HomeComponent,
    DeathComponent,
    CombatRoom,
)
from ..entitas import Matcher


###################################################################################################################################################################
def _build_dungeon_exit_message(dungeon_name: str, home_stage_name: str) -> str:
    """生成退出副本返回家园场景的提示消息。"""
    return (
        f"# 提示！副本：{dungeon_name} 结束，返回家园场景：{home_stage_name}\n"
        f"（关于「副本」及进出副本的具体设定，见你的「游戏设定」与「全局规则」。）"
    )


###################################################################################################################################################################
def exit_dungeon(dbg_game: DBGGame, dungeon: Dungeon) -> Tuple[bool, str]:
    """
    退出副本并将角色传送回家园。

    流程分为两个阶段：
      1) 检查阶段 —— 仅读取、验证，不修改任何状态，允许早期返回。
      2) 执行阶段 —— 一旦进入就不可能中断，所有操作均为断言或动作。
    """

    # =========================================================================
    # 阶段 1：检查（零状态变更，允许 return）
    # =========================================================================

    current_room = dungeon.rooms[dungeon.current_room_index]

    # 战斗房间必须处于战斗后状态才能退出（无论胜负）
    if isinstance(current_room, CombatRoom):
        if not current_room.combat.is_post_combat:
            logger.error("当前不处于战斗后状态，无法退出副本！必须先完成战斗。")
            return False, "战斗未结束，无法退出"

    # 确保存在远征队成员
    party_member_entities = dbg_game.get_group(
        Matcher(all_of=[PartyMemberComponent])
    ).entities.copy()
    assert len(party_member_entities) > 0, "没有找到远征队成员"

    # 确保存在家园场景
    home_stages = dbg_game.get_group(Matcher(all_of=[HomeComponent])).entities.copy()
    assert len(home_stages) >= 1, "必须存在至少一个家园场景！"
    dest_stage = next(iter(home_stages))

    # =========================================================================
    # 阶段 2：执行（不可中断，不回退）
    # =========================================================================

    # 传送远征队成员回家
    for party_member_entity in party_member_entities:
        dbg_game.add_human_message(
            party_member_entity,
            HumanMessage(
                content=_build_dungeon_exit_message(dungeon.name, dest_stage.name),
                dungeon_lifecycle_completion=dungeon.name,
            ),
        )
        stage_transition(dbg_game, {party_member_entity}, dest_stage)

    # 恢复所有远征队成员状态
    for party_member_entity in party_member_entities:
        if party_member_entity.has(DeathComponent):
            logger.info(f"移除死亡组件: {party_member_entity.name}")
            party_member_entity.remove(DeathComponent)

        full_stats = compute_character_stats(party_member_entity)
        set_character_hp(party_member_entity, full_stats.max_hp)
        logger.info(
            f"恢复满血: {party_member_entity.name} 生命值 = {full_stats.max_hp}/{full_stats.max_hp}"
        )

        assert party_member_entity.has(PartyMemberComponent)
        party_member_entity.remove(PartyMemberComponent)
        logger.info(f"从远征队移除: {party_member_entity.name}")

    # 离开战斗房间时清除残留战斗状态
    if isinstance(current_room, CombatRoom):
        clear_combat_state(dbg_game)

    logger.info(f"exit_dungeon 完成: {dungeon.name}")
    return True, "成功退出副本"
