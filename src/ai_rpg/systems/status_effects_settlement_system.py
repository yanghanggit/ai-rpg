"""状态效果结算系统模块。

该模块实现了游戏中的状态效果结算系统，负责在每个战斗回合开始前自动处理所有实体的状态效果。
系统会递减状态效果的持续时间，移除已过期的效果，并向实体发送相应的通知消息。

主要功能：
- 在战斗回合开始前自动结算状态效果
- 递减所有状态效果的持续回合数
- 移除持续时间为0的已过期状态效果
- 向角色发送状态效果移除的通知消息
- 记录结算过程的详细日志

结算机制：
- 该系统作为 ExecuteProcessor 在每个游戏循环中执行
- 仅在战斗进行中且非第一回合时执行结算
- 使用 CombatStatsComponent 管理状态效果
- 自动向实体的消息系统发送变更通知

使用场景：
- 战斗回合转换时的状态效果更新
- 临时增益/减益效果的自动管理
- 持续伤害/治疗效果的回合计数
- 控制效果（眩晕、沉默等）的持续时间管理

Note:
    该系统应该在 DrawCardsActionSystem 之前执行，
    确保角色在生成新卡牌时能够基于最新的状态效果做出决策。
"""

import copy
from typing import Final, List, final, override
from loguru import logger
from ..entitas import Entity, ExecuteProcessor, Matcher
from ..game.tcg_game import TCGGame
from ..models import CombatStatsComponent, StatusEffect


#######################################################################################################################################
def _format_removed_status_effects_message(removed_effects: List[StatusEffect]) -> str:
    """
    格式化被移除的状态效果列表为通知消息。

    Args:
        removed_effects: 被移除的状态效果列表

    Returns:
        str: 格式化的状态效果移除通知消息
    """
    effects_text = (
        "\n".join([f"- {e.name}: {e.description}" for e in removed_effects])
        if len(removed_effects) > 0
        else "- 无"
    )

    return f"""# 通知！如下 状态效果(status_effects) 被移除

{effects_text}"""


#######################################################################################################################################
@final
class StatusEffectsSettlementSystem(ExecuteProcessor):
    """
    状态效果结算系统。

    在每个游戏循环中自动执行状态效果的结算逻辑：
    1. 检查当前是否在战斗中
    2. 跳过第一回合（第一回合不需要结算）
    3. 为所有参与战斗的实体结算状态效果
    4. 发送状态效果变更通知
    """

    def __init__(self, game_context: TCGGame) -> None:
        """
        初始化状态效果结算系统。

        Args:
            game_context: TCG游戏上下文对象
        """
        self._game: Final[TCGGame] = game_context

    ####################################################################################################################################
    @override
    async def execute(self) -> None:
        """
        执行状态效果结算操作。

        该方法在每个游戏循环中被调用，负责：
        1. 检查战斗状态（非战斗中不执行）
        2. 检查回合数（第一回合不执行）
        3. 获取所有具有战斗属性的实体
        4. 为每个实体结算状态效果
        5. 发送状态效果移除通知

        Returns:
            None

        Note:
            - 仅在战斗进行中执行
            - 第一回合不执行结算（角色刚生成初始状态）
            - 使用 CombatStatsComponent 作为查询条件
            - 结算过程中会修改实体的状态效果列表
        """
        # 检查是否在战斗中
        if not self._game.current_combat_sequence.is_ongoing:
            return

        # 检查当前回合数（第一回合不需要结算状态效果）
        current_rounds_count = len(self._game.current_combat_sequence.current_rounds)
        if current_rounds_count <= 1:
            logger.debug("StatusEffectsSettlementSystem: 第一回合，跳过状态效果结算")
            return

        logger.debug(
            f"StatusEffectsSettlementSystem: 开始结算第{current_rounds_count}回合的状态效果"
        )

        # 获取所有参与战斗的实体（拥有 CombatStatsComponent 的实体）
        combat_entities = self._game.get_group(
            Matcher(CombatStatsComponent)
        ).entities.copy()

        # 为每个实体结算状态效果
        for entity in combat_entities:
            self._process_entity_status_effects_settlement(entity)

    ####################################################################################################################################
    def _process_entity_status_effects_settlement(self, entity: Entity) -> None:
        """
        处理单个实体的状态效果结算。

        为指定实体结算状态效果，并发送更新消息给角色。
        该方法会调用内部的 _settle_status_effects 方法执行实际的结算逻辑。

        Args:
            entity: 需要结算状态效果的实体

        Returns:
            None

        Note:
            - 结算后会向实体发送状态效果移除通知
            - 使用游戏消息系统发送通知
        """
        remaining_effects, removed_effects = self._settle_status_effects(entity)

        logger.debug(
            f"StatusEffectsSettlementSystem: {entity.name} => "
            f"remaining: {len(remaining_effects)}, removed: {len(removed_effects)}"
        )

        # 如果有状态效果被移除，发送通知消息
        if len(removed_effects) > 0:
            updated_status_effects_message = _format_removed_status_effects_message(
                removed_effects
            )
            self._game.add_human_message(entity, updated_status_effects_message)

    ####################################################################################################################################
    def _settle_status_effects(
        self, entity: Entity
    ) -> tuple[List[StatusEffect], List[StatusEffect]]:
        """
        结算单个实体的状态效果。

        将实体的所有状态效果持续回合数减1，并移除持续回合数为0的效果。
        这是状态效果结算的核心逻辑。

        处理流程：
        1. 获取实体的 CombatStatsComponent
        2. 遍历所有状态效果
        3. 将每个效果的 duration 减1
        4. 将 duration > 0 的效果保留，duration <= 0 的效果移除
        5. 更新实体的状态效果列表

        Args:
            entity: 需要结算状态效果的实体

        Returns:
            tuple: (剩余的状态效果列表, 被移除的状态效果列表)

        Note:
            - 使用深拷贝避免修改原始效果对象
            - duration 最小值为 0
            - 结算后会直接更新实体的 status_effects 列表
        """
        combat_stats_comp = entity.get(CombatStatsComponent)
        assert combat_stats_comp is not None, "Entity must have CombatStatsComponent"

        remaining_effects: List[StatusEffect] = []
        removed_effects: List[StatusEffect] = []

        for status_effect in combat_stats_comp.status_effects:
            # 效果回合数扣除
            status_effect.duration -= 1
            status_effect.duration = max(0, status_effect.duration)

            # status_effect持续回合数大于0，继续保留，否则移除
            if status_effect.duration > 0:
                # 添加到剩余列表
                remaining_effects.append(status_effect)
            else:
                # 添加到移除列表（使用深拷贝保存被移除的效果信息）
                removed_effects.append(copy.copy(status_effect))

        # 更新角色的状态效果列表，只保留剩余的效果
        combat_stats_comp.status_effects = remaining_effects

        logger.debug(
            f"_settle_status_effects: {entity.name} => "
            f"remaining: {len(remaining_effects)}, removed: {len(removed_effects)}"
        )

        # 返回结算结果
        return remaining_effects, removed_effects

    ####################################################################################################################################
