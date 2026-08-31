"""
战斗堆拆除系统模块
"""

from typing import Final, final, override

from loguru import logger

from ..entitas import ExecuteProcessor, Matcher
from ..game.dbg_game import DBGGame
from ..models import (
    ActorComponent,
    DeckComponent,
    DiscardPileComponent,
    DrawPileComponent,
    EquippedGearComponent,
    ExhaustPileComponent,
    InventoryComponent,
)


#######################################################################################################################################
@final
class CombatPileTeardownSystem(ExecuteProcessor):
    """
    战斗结束后清空并移除三个战斗临时子堆组件。
    """

    def __init__(self, game: DBGGame) -> None:
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    def _return_equipped_gear(self) -> None:
        """战斗结束时，收集所有角色实体上的 EquippedGearComponent 装备，归还玩家背包。"""
        gear_entities = self._game.get_group(
            Matcher(EquippedGearComponent)
        ).entities.copy()
        if not gear_entities:
            return

        # 获取玩家实体及其背包组件，准备归还装备
        player_entity = self._game.get_player_entity()
        assert player_entity is not None, "玩家实体不存在！"
        assert player_entity.has(InventoryComponent), "玩家实体缺少 InventoryComponent"
        inventory = player_entity.get(InventoryComponent)

        # 遍历所有装备实体，将其装备归还到玩家背包，并移除 EquippedGearComponent
        for entity in gear_entities:
            equipped = entity.get(EquippedGearComponent)
            inventory.items.extend(equipped.items)
            entity.remove(EquippedGearComponent)
            logger.debug(
                f"CombatPileTeardownSystem: {entity.name} 的 "
                f"{len(equipped.items)} 件装备已归还玩家背包"
            )

    ####################################################################################################################################
    @override
    async def execute(self) -> None:

        logger.debug("CombatPileTeardownSystem: 执行战斗堆拆除系统")

        if not self._game.current_dungeon_combat_room.combat.is_post_combat:
            logger.debug("CombatPileTeardownSystem: 当前非战斗后阶段，跳过")
            return

        # 战斗结束：归还所有当前行动者登记的装备到玩家背包
        self._return_equipped_gear()

        entities = self._game.get_group(
            Matcher(
                ActorComponent,
                DeckComponent,
                DrawPileComponent,
                DiscardPileComponent,
                ExhaustPileComponent,
            )
        ).entities.copy()

        if not entities:
            logger.debug("CombatPileTeardownSystem: 没有符合条件的实体，跳过")
            return

        logger.debug(f"CombatPileTeardownSystem: 清理 {len(entities)} 个实体的战斗子堆")

        for entity in entities:

            draw_pile = entity.get(DrawPileComponent)
            discard_pile = entity.get(DiscardPileComponent)
            exhaust_pile = entity.get(ExhaustPileComponent)

            total = (
                len(draw_pile.cards)
                + len(draw_pile.retained_cards)
                + len(discard_pile.cards)
                + len(exhaust_pile.cards)
            )

            # 清空三个战斗子堆（含 DrawPile 的 retain 保留队列；副本直接丢弃，原始牌在 DeckComponent 中完整保留）
            draw_pile.cards.clear()
            draw_pile.retained_cards.clear()
            discard_pile.cards.clear()
            exhaust_pile.cards.clear()

            # 移除战斗临时组件
            entity.remove(DrawPileComponent)
            entity.remove(DiscardPileComponent)
            entity.remove(ExhaustPileComponent)

            deck_comp = entity.get(DeckComponent)
            logger.debug(
                f"[{entity.name}] 战斗子堆已清理（丢弃 {total} 张副本）"
                f"，DeckComponent 原始牌库保留 {len(deck_comp.cards)} 张"
            )
