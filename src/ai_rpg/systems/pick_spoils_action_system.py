"""从 Spoils 领取奖励系统：当前仅实现卡牌子操作（加入牌库并标记已领取）。"""

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
    """响应 PickSpoilsAction，按 reward_kind 路由领取结果；当前仅支持卡牌（追加进 DeckComponent 并标记 Spoils claimed）。"""

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
            assert (
                not spoils_comp.claimed
            ), f"{entity.name} 的 Spoils 已领取，不能重复领取"

            # 追加领取的卡（保留其 uuid / source）
            deck_comp.cards.append(action.card)

            # 3 选 1：标记已领取；组件与候选保留（作为“已生成”守卫，并供回看）
            entity.replace(SpoilsComponent, entity.name, spoils_comp.cards, True)

            logger.info(
                f"[PickSpoilsActionSystem] {entity.name} 已从 Spoils 领取"
                f"「{action.card.name}」加入牌库（当前 {len(deck_comp.cards)} 张），"
                f"Spoils 保留为已领取"
            )
