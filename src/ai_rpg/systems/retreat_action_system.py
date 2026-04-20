"""撤退动作系统模块

该模块实现战斗中远征队成员的撤退处理系统，负责响应 RetreatAction 组件并执行撤退逻辑。

主要功能：
- 响应 RetreatAction 组件的添加事件
- 为撤退角色标记死亡状态
- 生成并添加撤退叙事消息到角色上下文
- 记录撤退事件到日志

执行时机：
- 在 PlayCardsActionSystem 之后
- 在 ArbitrationActionSystem 之前
- 仅在战斗进行中（is_ongoing）阶段执行

撤退流程：
1. RetreatActionSystem 标记死亡并添加叙事消息
2. CombatOutcomeSystem 检测死亡并触发战斗失败
3. 调用方执行 exit_dungeon_and_return_home 返回家园
"""

from typing import final, override
from loguru import logger
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..models import RetreatAction, ExpeditionMemberComponent, DeathComponent
from ..game.tcg_game import TCGGame


###################################################################################################################################################################
def _generate_retreat_message(dungeon_name: str, stage_name: str) -> str:
    """生成撤退提示消息

    Args:
        dungeon_name: 地下城名称
        stage_name: 当前关卡名称

    Returns:
        str: 格式化的撤退提示消息
    """
    return f"""# 提示！战斗撤退：从地下城 {dungeon_name} 的关卡 {stage_name} 撤退

你选择了战斗中撤退。所有同伴视为战斗失败。战斗结束后将返回家园。"""


###################################################################################################################################################################
@final
class RetreatActionSystem(ReactiveProcessor):
    """撤退动作系统

    响应 RetreatAction 组件的添加，为远征队成员执行撤退处理。

    处理逻辑：
    - 为角色添加 DeathComponent 标记
    - 生成撤退叙事消息并写入角色上下文
    - 记录撤退事件

    Note:
        撤退处理只做状态标记，实际的战斗结束和场景传送由其他系统负责：
        - CombatOutcomeSystem 检测死亡并触发战斗失败流程
        - exit_dungeon_and_return_home 执行场景传送和状态重置
    """

    def __init__(self, game: TCGGame) -> None:
        super().__init__(game)
        self._game: TCGGame = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(RetreatAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        """过滤条件：必须有 RetreatAction 和 ExpeditionMemberComponent"""
        return entity.has(RetreatAction) and entity.has(ExpeditionMemberComponent)

    ####################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        """处理撤退动作

        仅在战斗进行中（is_ongoing）时执行撤退处理。

        Args:
            entities: 包含 RetreatAction 的实体列表
        """

        # 状态守卫：仅在战斗进行中执行撤退处理
        if not self._game.current_dungeon.is_ongoing:
            logger.debug("RetreatActionSystem: 战斗未进行中，跳过撤退处理")
            return

        # 获取当前地下城信息，生成撤退消息需要使用地下城和关卡名称
        assert (
            self._game.current_dungeon is not None
        ), "RetreatActionSystem: current_dungeon is None"
        dungeon = self._game.current_dungeon

        # 处理每个撤退实体，执行撤退逻辑
        for entity in entities:
            self._process_retreat_action(entity, dungeon.name)

        # 标记当前战斗为撤退状态
        assert (
            dungeon.current_combat_room is not None
        ), "RetreatActionSystem: 当前房间没有战斗记录"
        dungeon.current_combat_room.combat.retreated = True

    ####################################################################################################################################
    def _process_retreat_action(self, entity: Entity, dungeon_name: str) -> None:
        """处理单个实体的撤退动作

        Args:
            entity: 包含 RetreatAction 和 ExpeditionMemberComponent 的实体
            dungeon_name: 地下城名称
        """
        assert entity.has(
            ExpeditionMemberComponent
        ), f"Entity {entity.name} must have ExpeditionMemberComponent"

        # 标记为死亡，后续 CombatOutcomeSystem 会检测并触发战斗失败流程
        entity.replace(DeathComponent, entity.name)
        logger.info(f"撤退: 角色 {entity.name} 标记为死亡")

        # 解析所在场景，生成撤退叙事消息并写入上下文
        stage_entity = self._game.resolve_stage_entity(entity)
        if stage_entity is None:
            logger.error(
                f"RetreatActionSystem: 无法找到角色 {entity.name} 所在的场景实体"
            )
            return

        retreat_message = _generate_retreat_message(dungeon_name, stage_entity.name)
        self._game.add_human_message(
            entity,
            retreat_message,
            dungeon_lifecycle_retreat=f"{dungeon_name}:{stage_entity.name}",
        )

        logger.info(
            f"战斗撤退处理完成: 角色={entity.name}, 地下城={dungeon_name}, 关卡={stage_entity.name}"
        )

    ####################################################################################################################################
