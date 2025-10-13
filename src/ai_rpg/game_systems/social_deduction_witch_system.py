from typing import final
from overrides import override
from ..entitas import ExecuteProcessor, Entity, Matcher
from ..game.tcg_game import TCGGame
from loguru import logger
from ..models import (
    InventoryComponent,
    ItemType,
    WitchComponent,
    DeathComponent,
)


###############################################################################################################################################
@final
class SocialDeductionWitchSystem(ExecuteProcessor):

    ###############################################################################################################################################
    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ###############################################################################################################################################
    @override
    async def execute(self) -> None:
        assert self._game._time_marker % 2 == 1, "时间标记必须是奇数，是夜晚"
        logger.info(f"夜晚 {self._game._time_marker // 2 + 1} 开始")
        logger.info("女巫请睁眼，选择你要救的玩家或毒的玩家")

        # 临时先这么写！
        alive_witch_entities = self._game.get_group(
            Matcher(
                all_of=[WitchComponent],
                none_of=[DeathComponent],
            )
        ).entities.copy()

        if len(alive_witch_entities) == 0:
            logger.warning("当前没有存活的女巫，无法进行击杀")
            return

        assert len(alive_witch_entities) == 1, "女巫不可能有多个"
        witch_entity = next(iter(alive_witch_entities))
        assert witch_entity is not None, "女巫实体不可能为空"

        logger.debug(f"当前女巫实体 = {witch_entity.name}")

        # 更新女巫的道具信息
        self._update_item_info(witch_entity)

    ################################################################################################################################################
    # 更新道具的信息
    def _update_item_info(self, witch_entity: Entity) -> None:

        assert witch_entity.has(WitchComponent)
        assert witch_entity.has(InventoryComponent)

        existing_update_item_messages = self._game.find_human_messages_by_attribute(
            actor_entity=witch_entity,
            attribute_key="witch_items",
            attribute_value=witch_entity.name,
        )

        if len(existing_update_item_messages) > 0:
            logger.debug(
                f"删除 entity {witch_entity.name} 之前的道具信息提示消息 {existing_update_item_messages}"
            )
            self._game.delete_human_messages_by_attribute(
                actor_entity=witch_entity,
                human_messages=existing_update_item_messages,
            )

        inventory_component = witch_entity.get(InventoryComponent)
        assert inventory_component is not None
        if len(inventory_component.items) == 0:
            self._game.append_human_message(
                witch_entity,
                f"""# 提示！你目前没有任何道具了。""",
                witch_items=witch_entity.name,
            )
        else:

            for item in inventory_component.items:

                assert (
                    item.type == ItemType.CONSUMABLE
                ), f"女巫的道具只能是消耗品类型，现在是 {item.type}"
                if item.type != ItemType.CONSUMABLE:
                    continue

                self._game.append_human_message(
                    witch_entity,
                    f"""# 提示！你目前拥有道具: {item.name}。\n{item.model_dump_json()}""",
                    witch_items=witch_entity.name,
                )

    ###############################################################################################################################################
