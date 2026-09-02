"""
副本开场房间动作模块（仅开场房间/OpeningRoom 相关）
"""

from typing import Tuple

from loguru import logger

from ..entitas import Matcher
from ..game.dbg_game import DBGGame
from ..models import (
    CardPoolComponent,
    DeathComponent,
    DeckComponent,
    GenerateCardPoolAction,
    PartyMemberComponent,
)


###################################################################################################################################################################
def activate_generate_card_pool(
    dbg_game: DBGGame,
) -> Tuple[bool, str]:
    """
    为当前开场房间内的所有队伍成员激活卡池生成动作（GenerateCardPoolAction）。

    由外部入口（CLI / API）显式调用，随后推动 _dungeon_opening_room_pipeline.process()
    让 GenerateCardPoolActionSystem 响应并生成卡池。
    """

    # 检查当前是否在玩家的副本阶段
    if not dbg_game.is_player_in_dungeon_stage:
        error_msg = "激活卡池生成失败：玩家不在副本场景中"
        logger.error(error_msg)
        return False, error_msg

    # 检查当前副本房间是否为开场房间
    if not dbg_game.is_current_room_dungeon_opening:
        error_msg = "当前副本房间不是开场房间，无法生成卡池"
        logger.error(error_msg)
        return False, error_msg

    # 状态守卫：卡池生成依赖开场初始化（叙事 + 牌库初始化）已完成
    if not dbg_game.current_dungeon_opening_room.initialized:
        error_msg = "开场房间尚未初始化（叙事 + 牌库），无法生成卡池"
        logger.error(error_msg)
        return False, error_msg

    # 获取当前副本中所有队伍成员实体，用于为他们添加卡池生成动作组件
    party_member_entities = dbg_game.get_group(
        Matcher(all_of=[PartyMemberComponent])
    ).entities.copy()
    assert (
        len(party_member_entities) > 0
    ), "激活卡池生成失败: 没有找到队伍成员, 至少有一个player"

    # 幂等守卫：若任一队伍成员已持有卡池组件，说明卡池已生成，拒绝重复生成
    already_generated = [
        e.name for e in party_member_entities if e.has(CardPoolComponent)
    ]
    if already_generated:
        error_msg = (
            f"卡池已生成（{already_generated} 已持有 CardPoolComponent），无需重复生成"
        )
        logger.warning(error_msg)
        return False, error_msg

    # 为每个队伍成员添加卡池生成动作组件
    for party_member_entity in party_member_entities:
        assert party_member_entity.has(
            PartyMemberComponent
        ), f"角色 {party_member_entity.name} 缺少 PartyMemberComponent"
        assert party_member_entity.has(
            DeckComponent
        ), f"队伍成员 {party_member_entity.name} 缺少 DeckComponent"
        assert not party_member_entity.has(
            DeathComponent
        ), f"队伍成员 {party_member_entity.name} 已死亡，无法生成卡池"

        party_member_entity.replace(
            GenerateCardPoolAction,
            party_member_entity.name,
        )
        logger.debug(f"为角色 {party_member_entity.name} 添加卡池生成动作组件")

    return (
        True,
        f"成功为 {len(party_member_entities)} 个队伍成员激活卡池生成动作",
    )
