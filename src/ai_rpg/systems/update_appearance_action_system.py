"""外观更新动作系统模块。

处理玩家在家园场景中装备时装（CostumeItem）的动作，
将 InventoryComponent 中指定时装的描述合成到 AppearanceComponent.appearance。
"""

from typing import final, override
from loguru import logger
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    UpdateAppearanceAction,
    AppearanceComponent,
    InventoryComponent,
)
from ..models.items import ItemType


@final
class UpdateAppearanceActionSystem(ReactiveProcessor):

    def __init__(self, game: TCGGame) -> None:
        super().__init__(game)
        self._game: TCGGame = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(UpdateAppearanceAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(
            UpdateAppearanceAction, AppearanceComponent, InventoryComponent
        )

    ####################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self._process_update_appearance_action(entity)

    ####################################################################################################################################
    def _process_update_appearance_action(self, entity: Entity) -> None:
        """处理外观更新动作，将背包内指定时装应用到角色外观。"""

        action = entity.get(UpdateAppearanceAction)
        inventory = entity.get(InventoryComponent)
        appearance_comp = entity.get(AppearanceComponent)

        # 从随身背包中找到目标时装
        costume = next(
            (
                item
                for item in inventory.items
                if item.name == action.item_name and item.type == ItemType.COSTUME_ITEM
            ),
            None,
        )

        if costume is None:
            logger.warning(
                f"外观更新失败: 角色 {entity.name} 背包中找不到时装 {action.item_name!r}"
            )
            self._game.add_human_message(
                entity=entity,
                message_content=f"# 提示！外观更新失败，背包中找不到时装「{action.item_name}」。",
            )
            return

        new_appearance = f"{appearance_comp.base_body}，{costume.description}"
        entity.replace(
            AppearanceComponent,
            appearance_comp.name,
            appearance_comp.base_body,
            new_appearance,
            costume.name,
        )

        logger.debug(f"角色 {entity.name} 外观已更新，当前时装: {costume.name!r}")
        self._game.add_human_message(
            entity=entity,
            message_content=f"# 外观已更新\n你穿上了「{costume.name}」，外观描述已更新。",
        )
