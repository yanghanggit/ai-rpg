"""
副本进入模块 —— 组建远征队并传送至副本第一关

enter_dungeon 是进入副本的唯一入口。
"""

from typing import Set, Tuple
from loguru import logger
from ..models.dungeon import CombatRoom
from ..game.dbg_game import DBGGame
from ..game.dbg_combat_processor import assert_no_residual_combat_state
from ..game.rpg_stage_transition import stage_transition
from ..models import (
    Dungeon,
    DungeonComponent,
    Combat,
    HumanMessage,
    PartyMemberComponent,
    PartyRosterComponent,
    DeathComponent,
    CombatState,
)
from ..entitas import Entity, Matcher
from ..utils import prompt_builder
from .dungeon_archive_action import notify_dungeon_director_entered


###################################################################################################################################################################
@prompt_builder
def _build_dungeon_enter_message(dungeon_name: str, stage_name: str) -> str:
    """生成进入副本第一关的传送提示消息。"""
    return (
        f"# 进入副本：{dungeon_name}，开始关卡场景：{stage_name}\n"
        f"（关于「副本」及进出副本的具体设定，见你的「游戏设定」与「全局规则」。）"
    )


###################################################################################################################################################################
def enter_dungeon(dbg_game: DBGGame, dungeon: Dungeon) -> Tuple[bool, str]:
    """组建远征队并传送至副本第一关，启动首个战斗序列。

    流程分为两个阶段：
      1) 检查阶段 —— 仅读取、验证，不修改任何状态，允许早期返回。
      2) 执行阶段 —— 一旦进入就不可能中断，所有操作均为断言或动作。
    """

    # =========================================================================
    # 阶段 1：检查（零状态变更，允许 return）
    # =========================================================================

    # 副本尚未通过 setup_dungeon 创建实体
    assert (
        dungeon.setup_entities
    ), f"{dungeon.name} 副本尚未 setup_entities，请先调用 setup_dungeon"
    if not dungeon.setup_entities:
        error_msg = (
            f"enter_dungeon 失败: {dungeon.name} 实体尚未创建，请先调用 setup_dungeon"
        )
        logger.error(error_msg)
        return False, error_msg

    # 已经进入过副本（current_room_index 应仍为 -1）
    assert dungeon.current_room_index == -1, f"enter_dungeon 失败: {dungeon.name} "
    if dungeon.current_room_index >= 0:
        error_msg = (
            f"enter_dungeon 失败: {dungeon.name} "
            f"current_room_index={dungeon.current_room_index}，期望值为 -1（已 setup 未进入）"
        )
        logger.error(error_msg)
        return False, error_msg

    # 副本无房间数据
    assert len(dungeon.rooms) > 0, f"enter_dungeon 失败: {dungeon.name} 没有房间数据"
    if len(dungeon.rooms) == 0:
        error_msg = f"enter_dungeon 失败: {dungeon.name} 没有房间数据"
        logger.error(error_msg)
        return False, error_msg

    # 首间
    enter_room = dungeon.rooms[0]

    # 关卡实体必须存在
    stage_entity = dbg_game.get_stage_entity(enter_room.stage.name)
    assert stage_entity is not None, f"{enter_room.stage.name} 没有对应的 stage 实体！"
    assert stage_entity.has(
        DungeonComponent
    ), f"{enter_room.stage.name} 没有 DungeonComponent 组件！"

    # 确保此时不存在任何远征队标记（PartyMemberComponent）
    party_members = dbg_game.get_group(Matcher(all_of=[PartyMemberComponent])).entities
    assert (
        len(party_members) == 0
    ), f"enter_dungeon 失败: 进入前已存在 {len(party_members)} 个远征队成员，请先退出当前副本"

    # =========================================================================
    # 阶段 2：执行（不可中断，不回退）
    # =========================================================================

    # 选择远征队成员并挂载 PartyMemberComponent
    player_entity = dbg_game.get_player_entity()
    assert player_entity is not None, "玩家实体不存在！"
    party_member_entities: Set[Entity] = {player_entity}
    logger.info(f"玩家 {player_entity.name} 将参与远征")
    if player_entity.has(PartyRosterComponent):
        for member_name in player_entity.get(PartyRosterComponent).members:
            member_entity = dbg_game.get_actor_entity(member_name)
            assert (
                member_entity is not None
            ), f"远征队名单中的成员 {member_name!r} 不存在！"
            party_member_entities.add(member_entity)
            logger.info(f"按名单将 {member_name} 加入远征队")
    logger.info(
        f"最终远征队成员 ({len(party_member_entities)}): "
        f"{[e.name for e in party_member_entities]}"
    )
    for party_member in party_member_entities:
        party_member.replace(PartyMemberComponent, party_member.name)
        logger.debug(
            f"将 {party_member.name} 添加 PartyMemberComponent 组件，标记为远征队成员"
        )

    assert len(party_member_entities) > 0, "没有选择任何远征队成员，无法进入副本"
    for party_member in party_member_entities:
        assert not party_member.has(
            DeathComponent
        ), f"远征队成员 {party_member.name} 已死亡，无法进入副本"
        logger.info(f"远征队成员: {party_member.name}，目标副本：{dungeon.name}")

    # 推进索引（-1 → 0）
    dungeon.current_room_index = 0
    current_room = dungeon.current_room
    assert current_room is not None, "此时 current_room 不可能为 None"

    # 生成并发送传送提示消息
    trans_message = _build_dungeon_enter_message(dungeon.name, stage_entity.name)
    for party_member in party_member_entities:
        dbg_game.add_human_message(
            party_member,
            HumanMessage(content=trans_message, dungeon_lifecycle_entry=dungeon.name),
        )

    # 执行场景传送
    stage_transition(dbg_game, party_member_entities, stage_entity)

    # 保底断言：pipeline 理应已清理完毕，此时不应存在残留战斗临时组件
    assert_no_residual_combat_state(dbg_game)

    # 若是战斗房间则创建战斗实例并初始化；入口房间仅做场景传送，不创建战斗
    if isinstance(current_room, CombatRoom):
        combat = Combat(name=stage_entity.name)
        combat.state = CombatState.INITIALIZATION
        current_room.combat = combat
    else:
        logger.info(
            f"enter_dungeon: 首间为 {current_room.type!r} 房间，跳过战斗初始化，等待玩家手动推进"
        )

    # 副本导演开局记录：以首个房间的起始设定作为其记忆的第一条事实
    notify_dungeon_director_entered(dbg_game, dungeon, current_room)

    logger.info(f"enter_dungeon 完成: {dungeon.name}")
    return True, f"成功进入副本: {dungeon.name}"
