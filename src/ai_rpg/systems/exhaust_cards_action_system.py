"""消耗牌动作系统（ExhaustCardsActionSystem）。

仅允许当前 turn 的行动者消耗手牌；消耗不消耗 energy、不推进行动顺序。
"""

from typing import Final, final
from loguru import logger
from overrides import override
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..models import (
    HandComponent,
    ExhaustPileComponent,
    ExhaustCardsAction,
    ActorComponent,
)
from ..game.tcg_game import TCGGame


#######################################################################################################################################
def _generate_discard_card_context_prompt(
    discard_cards_action: ExhaustCardsAction,
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
class ExhaustCardsActionSystem(ReactiveProcessor):
    """响应 ExhaustCardsAction 事件，将手牌移入消耗堆（ExhaustPile）。

    仅允许当前 turn 的行动者消耗手牌，且不消耗 energy、不推进行动顺序。
    自有牌归入 ExhaustPileComponent 并注入上下文；外来牌静默丢弃。
    """

    def __init__(self, game: TCGGame) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(ExhaustCardsAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(ExhaustCardsAction)
            and entity.has(HandComponent)
            and entity.has(ActorComponent)
            and entity.has(ExhaustPileComponent)
        )

    #######################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        if not self._game.current_dungeon.is_ongoing:
            logger.debug("ExhaustCardsActionSystem: 战斗未进行中，跳过消耗处理")
            return

        assert (
            len(entities) == 1
        ), "ExhaustCardsActionSystem: 一次只能处理一个消耗动作实体"
        logger.debug(
            f"ExhaustCardsActionSystem: 触发消耗处理，找到 {len(entities)} 个消耗实体"
        )

        current_rounds = self._game.current_dungeon.current_rounds
        assert (
            current_rounds is not None
        ), "ExhaustCardsActionSystem: current_rounds is None"

        last_round = self._game.current_dungeon.latest_round
        assert last_round is not None, "ExhaustCardsActionSystem: latest_round is None"

        for entity in entities:
            assert entity.name == self._game.get_current_turn_actor(last_round), (
                f"ExhaustCardsActionSystem: 消耗牌角色 {entity.name} 不是当前 turn 的行动者！"
                f" current_turn_actor={self._game.get_current_turn_actor(last_round)}"
            )

            discard_action = entity.get(ExhaustCardsAction)
            logger.debug(
                f"  [{discard_action.name}] 弃牌 → 卡牌: {discard_action.card.name}"
            )

            # 按对象身份从 HandComponent 移除目标卡牌
            hand_comp = entity.get(HandComponent)
            assert hand_comp is not None, f"{entity.name} 缺少 HandComponent"
            discarded_card = discard_action.card
            new_hand_cards = [c for c in hand_comp.cards if c is not discarded_card]
            hand_comp.cards = new_hand_cards

            # source 守卫：自有牌归档至 ExhaustPileComponent 并注入上下文
            # 外来牌（PostArbitrationActionSystem 塞入时未通知角色）静默丢弃，不注入上下文
            if discarded_card.source == entity.name:
                discard_comp = entity.get(ExhaustPileComponent)
                assert (
                    discard_comp is not None
                ), f"{entity.name} 缺少 ExhaustPileComponent"
                discard_comp.cards.append(discarded_card)
                logger.debug(
                    f"  [{entity.name}] 手牌 {len(hand_comp.cards) + 1} → {len(new_hand_cards)}，"
                    f"ExhaustPile 累计 {len(discard_comp.cards)} 张"
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
