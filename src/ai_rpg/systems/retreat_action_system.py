"""撤退动作系统模块"""

from typing import final, override, Dict, List
from loguru import logger
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..models import HumanMessage, RetreatAction, PartyMemberComponent, DeathComponent
from ..game.dbg_game import DBGGame


###################################################################################################################################################################
def _generate_retreat_message(dungeon_name: str, stage_name: str) -> str:
    """生成撤退提示消息"""
    return f"""# 提示！战斗撤退：从地下城 {dungeon_name} 的关卡 {stage_name} 撤退

你选择了战斗中撤退。所有同伴视为战斗失败。战斗结束后将返回家园。"""


###################################################################################################################################################################
@final
class RetreatActionSystem(ReactiveProcessor):
    """撤退动作系统"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: DBGGame = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(RetreatAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        """过滤条件：必须有 RetreatAction 和 PartyMemberComponent"""
        return entity.has(RetreatAction) and entity.has(PartyMemberComponent)

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        """处理撤退动作"""

        # 状态守卫：仅在战斗进行中执行撤退处理
        if not self._game.current_combat_room.combat.is_ongoing:
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
        self._game.current_combat_room.combat.retreated = True

    ####################################################################################################################################
    def _process_retreat_action(self, entity: Entity, dungeon_name: str) -> None:
        """处理单个实体的撤退动作"""
        assert entity.has(
            PartyMemberComponent
        ), f"Entity {entity.name} must have PartyMemberComponent"

        # 标记为死亡，后续 CombatOutcomeSystem 会检测并触发战斗失败流程
        entity.replace(DeathComponent, entity.name)
        logger.info(f"撤退: 角色 {entity.name} 标记为死亡")

        # 解析所在场景，生成撤退叙事消息并写入上下文
        stage_entity = self._game.resolve_stage_entity(entity)
        assert stage_entity is not None, f"Entity {entity.name} must be in a stage"

        # 生成撤退消息并写入上下文
        retreat_message = _generate_retreat_message(dungeon_name, stage_entity.name)
        self._game.add_human_message(
            entity,
            HumanMessage(
                content=retreat_message,
                dungeon_lifecycle_retreat=f"{dungeon_name}:{stage_entity.name}",
            ),
        )
        logger.info(
            f"战斗撤退处理完成: 角色={entity.name}, 地下城={dungeon_name}, 关卡={stage_entity.name}"
        )

    ####################################################################################################################################
