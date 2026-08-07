"""
副本退出模块 —— 退出副本并传送角色回家园

exit_dungeon 是退出副本的唯一入口。
"""

from typing import Set
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
)
from ..entitas import Matcher, Entity


###################################################################################################################################################################
def _generate_return_home_message(
    dungeon_name: str, destination_stage_name: str
) -> str:
    """生成返回家园的提示消息"""
    return (
        f"""# 提示！副本：{dungeon_name} 结束，返回家园场景：{destination_stage_name}"""
    )


###################################################################################################################################################################
def exit_dungeon(dbg_game: DBGGame, dungeon: Dungeon) -> None:
    """
    退出副本并将角色传送回家园
    """

    cs = dbg_game.current_combat_room.combat
    logger.debug(
        f"[return_home] 入参 dungeon={dungeon.name!r}, "
        f"world.dungeon={dbg_game._world.dungeon.name!r}, "
        f"is_ongoing={cs.is_ongoing}, is_post_combat={cs.is_post_combat}, "
        f"is_won={cs.is_won}, is_lost={cs.is_lost}"
    )

    # 严格要求：只能在战斗后状态退出（无论胜负）
    if not dbg_game.current_combat_room.combat.is_post_combat:
        logger.error(
            f"当前不处于战斗后状态，无法退出副本！"
            f"必须先完成战斗进入 post_combat 状态。"
        )
        return

    # 1. 验证并获取远征队成员
    party_member_entities = dbg_game.get_group(
        Matcher(all_of=[PartyMemberComponent])
    ).entities.copy()
    logger.debug(
        f"[return_home] 远征队成员({len(party_member_entities)}): "
        f"{[e.name for e in party_member_entities]}"
    )
    assert len(party_member_entities) > 0, "没有找到远征队成员"

    # 2. 获取家园场景实体
    home_stages: Set[Entity] = dbg_game.get_group(
        Matcher(all_of=[HomeComponent])
    ).entities.copy()
    logger.debug(
        f"[return_home] 家园场景({len(home_stages)}): "
        f"{[e.name for e in home_stages]}"
    )
    assert len(home_stages) >= 1, "必须存在至少一个家园场景！"

    # 3. 生成并发送返回提示消息，传送远征队成员回家
    dest_stage = next(iter(home_stages))

    for party_member_entity in party_member_entities:
        current_stage_entity = dbg_game.resolve_stage_entity(party_member_entity)
        current_stage_name = (
            current_stage_entity.name if current_stage_entity else "None"
        )
        logger.debug(
            f"[return_home] 传送 {party_member_entity.name} | "
            f"当前场景={current_stage_name!r} → 目标场景={dest_stage.name!r}"
        )

        dbg_game.add_human_message(
            party_member_entity,
            HumanMessage(
                content=_generate_return_home_message(dungeon.name, dest_stage.name),
                dungeon_lifecycle_completion=dungeon.name,
            ),
        )
        stage_transition(dbg_game, {party_member_entity}, dest_stage)

        after_stage_entity = dbg_game.resolve_stage_entity(party_member_entity)
        after_stage_name = after_stage_entity.name if after_stage_entity else "None"
        logger.debug(
            f"[return_home] 传送后 {party_member_entity.name} 当前场景={after_stage_name!r}"
        )

    # 4. 恢复所有远征队成员的战斗状态
    for party_member_entity in party_member_entities:
        # 移除死亡组件
        if party_member_entity.has(DeathComponent):
            logger.info(f"移除死亡组件: {party_member_entity.name}")
            party_member_entity.remove(DeathComponent)

        # 恢复生命值至满血
        full_stats = compute_character_stats(party_member_entity)
        set_character_hp(party_member_entity, full_stats.max_hp)
        logger.info(
            f"恢复满血: {party_member_entity.name} 生命值 = {full_stats.max_hp}/{full_stats.max_hp}"
        )

        # 解散远征队，移除PartyMemberComponent组件
        assert party_member_entity.has(PartyMemberComponent)
        party_member_entity.remove(PartyMemberComponent)
        logger.info(f"从远征队移除: {party_member_entity.name}")

    # 5. 最终场景确认
    for party_member_entity in party_member_entities:
        final_stage = dbg_game.resolve_stage_entity(party_member_entity)
        logger.debug(
            f"[return_home] 最终确认 {party_member_entity.name} 场景={final_stage.name if final_stage else 'None'!r}"
        )

    # 6. 清除战斗临时状态
    clear_combat_state(dbg_game)
