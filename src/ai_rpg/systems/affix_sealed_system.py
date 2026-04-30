"""AffixSealedSystem — 封印词条处理系统。

从所有持有 HandComponent 的实体中，将手牌里携带「封印」词条的卡牌
物化到实体级 AffixSealedComponent，供后续出牌/弃牌等系统直接查询组件。

职责：
- 扫描手牌，同步写入/清除 AffixSealedComponent
- 与抽牌系统解耦：无论手牌从何而来，封印状态都保持一致
"""

from typing import Final, final, override
from loguru import logger
from ..entitas import ExecuteProcessor, Matcher
from ..game.tcg_game import TCGGame
from ..models import (
    AffixSealedComponent,
    HandComponent,
)


#######################################################################################################################################
@final
class AffixSealedSystem(ExecuteProcessor):
    """封印词条同步系统。

    每帧扫描所有持有 HandComponent 的实体，将手牌中携带「封印」词条的卡牌
    副本写入 AffixSealedComponent；手牌无封印牌时清除组件。
    """

    def __init__(self, game: TCGGame) -> None:
        self._game: Final[TCGGame] = game

    #######################################################################################################################################
    @override
    async def execute(self) -> None:
        if not self._game.current_dungeon.is_ongoing:
            return

        for entity in self._game.get_group(Matcher(HandComponent)).entities.copy():
            hand_comp = entity.get(HandComponent)
            if hand_comp is None:
                continue

            sealed_cards = [
                card.model_copy()
                for card in hand_comp.cards
                if any(a.name == AffixSealedComponent.__name__ for a in card.affixes)
            ]

            if sealed_cards:
                first_affix = next(
                    (
                        a
                        for c in sealed_cards
                        for a in c.affixes
                        if a.name == AffixSealedComponent.__name__
                    ),
                    None,
                )
                desc = first_affix.data.get("description", "") if first_affix else ""
                entity.replace(AffixSealedComponent, entity.name, desc, sealed_cards)
                logger.debug(
                    f"[{entity.name}] AffixSealedComponent 写入封印牌: "
                    f"{[c.name for c in sealed_cards]}"
                )
            elif entity.has(AffixSealedComponent):
                entity.remove(AffixSealedComponent)
                logger.debug(f"[{entity.name}] 无封印牌，清除 AffixSealedComponent")
