"""从卡池挑选卡牌系统：将选中的候选卡加入牌库，并清空卡池（零 LLM）。"""

from typing import Dict, Final, List, final, override

from loguru import logger

from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..models import (
    ActorComponent,
    SpoilsComponent,
    DeathComponent,
    DeckComponent,
    PickCardAction,
)


#######################################################################################################################################
@final
class PickCardActionSystem(ReactiveProcessor):
    """响应 PickCardFromPoolAction，把选中卡追加进 DeckComponent 并清空 SpoilsComponent。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(PickCardAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(PickCardAction)
            and entity.has(ActorComponent)
            and entity.has(DeckComponent)
            and entity.has(SpoilsComponent)
            and not entity.has(DeathComponent)
        )

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        for entity in entities:
            action = entity.get(PickCardAction)
            assert action is not None, f"{entity.name} 缺少 PickCardFromPoolAction"

            deck_comp = entity.get(DeckComponent)
            assert deck_comp is not None, f"{entity.name} 缺少 DeckComponent"

            # 追加选中的卡（保留其 uuid / source）
            deck_comp.cards.append(action.card)

            # 3 选 1：消费掉整个卡池（其余候选丢弃）
            entity.remove(SpoilsComponent)

            logger.info(
                f"[PickCardFromPoolActionSystem] {entity.name} 已从卡池挑选"
                f"「{action.card.name}」加入牌库（当前 {len(deck_comp.cards)} 张），"
                f"卡池已清空"
            )
