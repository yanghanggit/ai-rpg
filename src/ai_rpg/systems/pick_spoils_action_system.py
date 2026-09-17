"""从 Spoils 领取奖励系统：当前仅实现卡牌子操作（从待领取队列出队、加入牌库并记入已领取队列）。"""

from typing import Dict, Final, List, final, override

from loguru import logger

from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..models import (
    ActorComponent,
    SpoilsComponent,
    DeathComponent,
    DeckComponent,
    PickSpoilsAction,
    SpoilRewardKind,
)


#######################################################################################################################################
@final
class PickSpoilsActionSystem(ReactiveProcessor):
    """响应 PickSpoilsAction，按 reward_kind 路由领取结果；当前仅支持卡牌（从 Spoils.candidate_cards 出队追加进 DeckComponent，并记入 Spoils.claimed_cards）。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(PickSpoilsAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(PickSpoilsAction)
            and entity.has(ActorComponent)
            and entity.has(SpoilsComponent)
            and not entity.has(DeathComponent)
        )

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        for entity in entities:
            action = entity.get(PickSpoilsAction)
            assert action is not None, f"{entity.name} 缺少 PickSpoilsAction"

            # 子操作路由：当前仅实现卡牌；未来可扩展 item / artifact
            assert (
                action.reward_kind == SpoilRewardKind.CARD
            ), f"{entity.name} 暂不支持的奖励类型: {action.reward_kind}"
            assert action.card is not None, f"{entity.name} 领取卡牌但 card 为空"

            deck_comp = entity.get(DeckComponent)
            assert deck_comp is not None, f"{entity.name} 缺少 DeckComponent"

            spoils_comp = entity.get(SpoilsComponent)
            assert spoils_comp is not None, f"{entity.name} 缺少 SpoilsComponent"
            # 当前 gameplay 只允许领一次：已领取过则拒绝（claimed_cards 非空即视为已领取）
            assert (
                not spoils_comp.claimed_cards
            ), f"{entity.name} 的 Spoils 已领取，不能重复领取"

            # 两队列维护：从待领取队列 candidate_cards 出队选中卡，追加进已领取队列 claimed_cards
            remaining_cards = [
                c for c in spoils_comp.candidate_cards if c is not action.card
            ]
            assert len(remaining_cards) == len(spoils_comp.candidate_cards) - 1, (
                f"{entity.name} 的 Spoils 待领取队列中找不到所选卡"
                f"「{action.card.name}」"
            )
            claimed_cards = [*spoils_comp.claimed_cards, action.card]

            # 追加领取的卡（保留其 uuid / source）
            deck_comp.cards.append(action.card)

            # 落盘：cards 少一张、claimed 多一张
            entity.replace(SpoilsComponent, entity.name, remaining_cards, claimed_cards)

            logger.info(
                f"[PickSpoilsActionSystem] {entity.name} 已从 Spoils 领取"
                f"「{action.card.name}」加入牌库（当前 {len(deck_comp.cards)} 张），"
                f"Spoils 待领取 {len(remaining_cards)} 张 / 已领取 {len(claimed_cards)} 张"
            )
