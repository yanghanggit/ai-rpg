"""
副本进入模块 —— 组建远征队并传送至副本第一关

enter_dungeon 是进入副本的唯一入口。
"""

from typing import Set
from loguru import logger
from ..game.dbg_game import DBGGame
from ..game.dbg_combat_processor import (
    set_character_hp,
    clear_combat_state,
    select_party_members,
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
def _generate_dungeon_entry_message(
    dungeon_name: str,
    dungeon_stage_name: str,
) -> str:
    """生成副本进入提示消息"""
    return f"""# 进入副本：{dungeon_name}，开始关卡场景：{dungeon_stage_name}"""


###################################################################################################################################################################
def _enter_dungeon_stage(
    dbg_game: DBGGame, dungeon: Dungeon, party_member_entities: Set[Entity]
) -> bool:
    """
    进入副本关卡并初始化战斗环境
    """
    if len(party_member_entities) == 0:
        logger.error("没有远征队成员不能进入副本!")
        return False

    # 1. 验证前置条件 - 获取当前关卡数据
    current_room = dungeon.current_room
    if current_room is None:
        logger.error("当前副本房间不存在，无法进入关卡")
        return False

    assert isinstance(current_room, CombatRoom), "当前副本房间必须是战斗房间"
    stage_model = current_room.stage
    assert stage_model is not None, f"{dungeon.name} 副本关卡数据异常！"

    # 2. 获取关卡实体
    stage_entity = dbg_game.get_stage_entity(stage_model.name)
    assert stage_entity is not None, f"{stage_model.name} 没有对应的stage实体！"

    assert stage_entity.has(
        DungeonComponent
    ), f"{stage_model.name} 没有DungeonComponent组件！"

    # 3. 生成并发送传送提示消息
    trans_message = _generate_dungeon_entry_message(
        dungeon.name,
        stage_entity.name,
    )

    for party_member in party_member_entities:
        dbg_game.add_human_message(
            party_member,
            HumanMessage(content=trans_message, dungeon_lifecycle_entry=dungeon.name),
        )

        if party_member.has(DeathComponent):
            logger.info(f"移除死亡组件: {party_member.name}")
            party_member.remove(DeathComponent)
            revived_stats = set_character_hp(party_member, 1)
            logger.info(
                f"恢复生命值: {party_member.name} 生命值 = {revived_stats.hp}/{revived_stats.max_hp}"
            )

    # 4. 执行场景传送
    stage_transition(dbg_game, party_member_entities, stage_entity)

    # 5. 创建战斗实例并初始化状态
    combat = Combat(name=stage_entity.name)
    combat.state = CombatState.INITIALIZATION
    current_room.combat = combat

    return True


###################################################################################################################################################################
def enter_dungeon(dbg_game: DBGGame, dungeon: Dungeon) -> tuple[bool, str]:
    """组建远征队并传送至副本第一关，启动首个战斗序列。"""
    if not dungeon.setup_entities:
        error_msg = (
            f"enter_dungeon 失败: {dungeon.name} 实体尚未创建，请先调用 setup_dungeon"
        )
        logger.error(error_msg)
        return False, error_msg

    if dungeon.current_room_index >= 0:
        error_msg = (
            f"enter_dungeon 失败: {dungeon.name} "
            f"current_room_index={dungeon.current_room_index}，期望值为 -1（已 setup 未进入）"
        )
        logger.error(error_msg)
        return False, error_msg

    # 确保全局不存在远征队成员（无人正在参与远征）
    party_members = dbg_game.get_group(Matcher(all_of=[PartyMemberComponent])).entities
    assert len(party_members) == 0, (
        f"enter_dungeon: 进入前必须无远征队成员，" f"当前存在 {len(party_members)} 个"
    )

    # 推进索引（-1 → 0），_enter_dungeon_stage 依赖此值判断首次进入消息
    dungeon.current_room_index = 0

    # 选择远征队成员
    party_member_entities = select_party_members(dbg_game)
    for party_member in party_member_entities:
        logger.info(f"远征队成员: {party_member.name}，目标副本：{dungeon.name}")

    # 传送并初始化战斗
    if not _enter_dungeon_stage(dbg_game, dungeon, party_member_entities):
        error_msg = f"enter_dungeon 失败: 无法进入第一关 {dungeon.name}"
        logger.error(error_msg)
        return False, error_msg

    # 清除上一场战斗的临时状态
    clear_combat_state(dbg_game)

    logger.info(f"enter_dungeon 完成: {dungeon.name}")
    return True, f"成功进入副本: {dungeon.name}"
