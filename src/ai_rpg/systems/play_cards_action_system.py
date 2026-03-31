"""出牌动作系统模块。

处理战斗中角色的出牌动作，向角色的对话上下文添加出牌通知，
包含卡牌名称、目标、描述和卡牌属性（治疗/攻击/防御）。
仅在战斗进行中(ongoing)阶段执行。
"""

from typing import Final, final
from loguru import logger
from overrides import override
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..models import (
    HandComponent,
    PlayCardsAction,
    ActorComponent,
)
from ..game.tcg_game import TCGGame


#######################################################################################################################################
@final
class PlayCardsActionSystem(ReactiveProcessor):
    """出牌动作系统。

    响应 PlayCardsAction 组件的添加事件，向角色发送出牌通知消息。
    通知包含卡牌的完整信息：名称、目标、描述和属性（治疗/攻击/防御）。

    触发条件：
    - 实体添加 PlayCardsAction 组件
    - 战斗序列处于进行中(ongoing)状态

    执行流程：
    1. 发送出牌指令（第N回合使用卡牌）
    2. 添加AI出牌执行消息（卡牌详情）
    3. 为场景实体添加仲裁动作标记
    """

    def __init__(self, game: TCGGame) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(PlayCardsAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(PlayCardsAction)
            and entity.has(HandComponent)
            and entity.has(ActorComponent)
        )

    #######################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        """处理出牌动作。

        检查战斗是否进行中，如是则为每个出牌的角色生成通知消息并添加到其对话上下文。
        通知包含角色名、卡牌名、目标和卡牌完整数据(JSON)。
        """
        if not self._game.current_dungeon.is_ongoing:
            # 必须是 进行中的阶段！
            logger.debug("PlayCardsActionSystem: 战斗未进行中，跳过出牌处理")
            return

        assert len(entities) == 1, "PlayCardsActionSystem: 一次只能处理一个出牌动作实体"
        logger.debug(
            f"PlayCardsActionSystem: 触发出牌处理，找到 {len(entities)} 个出牌实体"
        )

        # 获取当前回合数
        current_rounds = self._game.current_dungeon.current_rounds
        assert (
            current_rounds is not None
        ), "PlayCardsActionSystem: current_rounds is None"

        last_round = self._game.current_dungeon.latest_round
        assert last_round is not None, "PlayCardsActionSystem: latest_round is None"

        logger.debug(
            f"PlayCardsActionSystem: 当前回合数 {len(current_rounds)}，最新回合状态: {'已完成' if last_round.is_round_completed else '未完成'}"
        )

        for entity in entities:
            action = entity.get(PlayCardsAction)
            logger.debug(
                f"  [{action.name}] 出牌 → 卡牌: {action.card.name}"
                f" | damage={action.card.damage} block={action.card.block}"
                f" | 目标: {action.targets}"
                f" | 行动叙事: {action.card.action}"
            )

            # 将出牌角色写入本回合 completed_actors
            if action.name not in last_round.completed_actors:
                last_round.completed_actors.append(action.name)
                logger.debug(
                    f"  completed_actors: {last_round.completed_actors} / {last_round.action_order}"
                )
