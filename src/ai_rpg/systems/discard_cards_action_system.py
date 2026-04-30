"""弃牌动作系统模块。

处理战斗中角色的主动弃牌动作，将指定手牌从 HandComponent 移入 DiscardDeckComponent，
并向角色的对话上下文注入弃牌通知（仅限自有牌）。
仅在战斗进行中(ongoing)阶段执行。弃牌不消耗能量、不推进行动顺序。
"""

from typing import Final, final
from loguru import logger
from overrides import override
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..models import (
    HandComponent,
    DiscardDeckComponent,
    DiscardCardsAction,
    ActorComponent,
)
from ..game.tcg_game import TCGGame


#######################################################################################################################################
def _generate_discard_card_context_prompt(
    discard_cards_action: DiscardCardsAction,
    round_number: int,
) -> str:
    """生成弃牌上下文消息，注入角色的对话历史，帮助 LLM 感知本回合弃牌情况。"""
    card = discard_cards_action.card
    return "\n".join(
        [
            f"【第 {round_number} 回合 · 弃牌】",
            f"你弃置了卡牌「{card.name}」。",
        ]
    )


#######################################################################################################################################
@final
class DiscardCardsActionSystem(ReactiveProcessor):
    """弃牌动作系统。

    响应 DiscardCardsAction 组件的添加事件，将指定手牌移入弃牌堆（DiscardDeckComponent），
    并向角色注入弃牌上下文消息。弃牌不消耗能量、不推进行动顺序。

    触发条件：
    - 实体添加 DiscardCardsAction 组件
    - 战斗序列处于进行中(ongoing)状态

    执行流程：
    1. 按对象身份从 HandComponent 中移除目标卡牌
    2. 若卡牌来源为本角色（source == entity.name），归入 DiscardDeckComponent 并注入上下文消息
       外来牌（PostArbitrationActionSystem 塞入，未通知角色）静默丢弃，不注入任何上下文
    """

    def __init__(self, game: TCGGame) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(DiscardCardsAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(DiscardCardsAction)
            and entity.has(HandComponent)
            and entity.has(ActorComponent)
            and entity.has(DiscardDeckComponent)
        )

    #######################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        if not self._game.current_dungeon.is_ongoing:
            logger.debug("DiscardCardsActionSystem: 战斗未进行中，跳过弃牌处理")
            return

        assert (
            len(entities) == 1
        ), "DiscardCardsActionSystem: 一次只能处理一个弃牌动作实体"
        logger.debug(
            f"DiscardCardsActionSystem: 触发弃牌处理，找到 {len(entities)} 个弃牌实体"
        )

        current_rounds = self._game.current_dungeon.current_rounds
        assert (
            current_rounds is not None
        ), "DiscardCardsActionSystem: current_rounds is None"

        for entity in entities:
            discard_action = entity.get(DiscardCardsAction)
            logger.debug(
                f"  [{discard_action.name}] 弃牌 → 卡牌: {discard_action.card.name}"
            )

            # 按对象身份从 HandComponent 移除目标卡牌
            hand_comp = entity.get(HandComponent)
            assert hand_comp is not None, f"{entity.name} 缺少 HandComponent"
            discarded_card = discard_action.card
            new_hand_cards = [c for c in hand_comp.cards if c is not discarded_card]
            hand_comp.cards = new_hand_cards

            # source 守卫：自有牌归档至 DiscardDeckComponent 并注入上下文
            # 外来牌（PostArbitrationActionSystem 塞入时未通知角色）静默丢弃，不注入上下文
            if discarded_card.source == entity.name:
                discard_comp = entity.get(DiscardDeckComponent)
                assert (
                    discard_comp is not None
                ), f"{entity.name} 缺少 DiscardDeckComponent"
                discard_comp.cards.append(discarded_card)
                logger.debug(
                    f"  [{entity.name}] 手牌 {len(hand_comp.cards) + 1} → {len(new_hand_cards)}，"
                    f"DiscardDeck 累计 {len(discard_comp.cards)} 张"
                )
                self._game.add_human_message(
                    entity=entity,
                    message_content=_generate_discard_card_context_prompt(
                        discard_cards_action=discard_action,
                        round_number=len(current_rounds),
                    ),
                )
            else:
                # PostArbitration 塞入时未告知角色，弃牌同样静默，保持上下文一致
                logger.debug(
                    f"  [{entity.name}] 外来牌 [{discarded_card.name}](source={discarded_card.source!r}) 静默丢弃"
                )
