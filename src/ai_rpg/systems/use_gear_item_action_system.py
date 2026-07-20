"""使用装备前置动作系统模块。"""

from typing import Dict, Final, List, final
from loguru import logger
from overrides import override
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..game.dbg_combat_processor import consume_energy, get_energy, remove_equipped_gear
from ..models import (
    AgentEvent,
    EquippedGearComponent,
    UseGearItemAction,
    GearItem,
)


#######################################################################################################################################
def _generate_gear_notice(
    target_name: str,
    item_name: str,
    round_number: int,
) -> str:
    """生成装备使用广播通知。"""
    return (
        f"【第 {round_number} 回合 · 装备行动】\n"
        f"「{target_name}」装备了「{item_name}」。"
    )


#######################################################################################################################################
@final
class UseGearItemActionSystem(ReactiveProcessor):
    """使用装备前置动作系统。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(UseGearItemAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(UseGearItemAction)

    #######################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:

        if not self._game.current_combat_room.combat.is_ongoing:
            logger.debug("UseGearItemActionSystem: 战斗未进行中，跳过")
            return

        # 不可能有多个
        assert (
            len(entities) == 1
        ), f"UseGearItemActionSystem: 同一时间不应有多个实体触发 UseGearItemAction，当前数量: {len(entities)}"
        logger.debug(f"UseGearItemActionSystem: 触发实体数量 {len(entities)}")

        # 取出触发实体
        entity = entities[0]

        # 准备数据
        action = entity.get(UseGearItemAction)

        # 校验 action.item 类型
        item = action.item
        assert isinstance(
            item, GearItem
        ), f"UseGearItemActionSystem: action.item 应为 GearItem，但实际类型为 {type(item)}"

        # 目标校验
        assert (
            len(action.targets) > 0
        ), "UseGearItemActionSystem: 使用装备必须指定至少一个目标"
        target_name = action.targets[0]
        logger.debug(
            f"UseGearItemActionSystem: 使用装备 '{item.name}' | cost={item.cost} | 目标: {action.targets}"
        )

        # 装备到目标实体。前置校验由 activate_use_gear 负责，这里只落地动作效果。
        target_entity = self._game.get_entity_by_name(target_name)
        assert (
            target_entity is not None
        ), f"UseGearItemActionSystem: 无法找到目标 {target_name}"
        assert (
            get_energy(target_entity) >= item.cost
        ), f"{target_entity.name} 能量不足！需要 energy={item.cost}，当前 energy={get_energy(target_entity)}"

        # 兜底，按理讲不应该发生
        remove_equipped_gear(self._game, item)

        # 装备动作落地
        target_entity.replace(
            EquippedGearComponent,
            target_entity.name,
            item.model_copy(deep=True),
        )
        logger.debug(
            f"UseGearItemActionSystem: [{entity.name}] 已为 [{target_name}] 装备 '{item.name}'"
        )

        # 消耗被装备目标本回合指定 energy；不调用 advance_turn ——
        # 行动权推进完全由 completed_actors（仅 pass turn 写入）决定，装备动作本身不结束任何人的回合
        if item.cost > 0:
            consume_energy(target_entity, item.cost)

        # 记录日志
        logger.debug(
            f"UseGearItemActionSystem: '{target_entity.name}' 装备消耗 {item.cost} 点 energy，剩余 {get_energy(target_entity)}"
        )

        # 向场景内所有存活角色广播装备使用通知
        round_number = len(self._game.current_combat_room.combat.rounds)
        stage_entity = self._game.resolve_stage_entity(entity)
        assert (
            stage_entity is not None
        ), f"UseGearItemActionSystem: 无法找到 {entity.name} 所在的场景实体"
        self._game.broadcast_to_stage(
            entity=entity,
            agent_event=AgentEvent(
                message=_generate_gear_notice(
                    target_entity.name,
                    item.name,
                    round_number,
                )
            ),
            exclude_entities={stage_entity},
        )
