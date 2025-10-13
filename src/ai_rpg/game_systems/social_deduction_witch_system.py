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
    WerewolfComponent,
    SeerComponent,
    VillagerComponent,
    WolfKillAction,
    SDWitchItemName,
    Item,
    WitchPoisonAction,
    WitchCureAction,
)
import random

# 解药	Healing Potion 或 Cure	用于救活被狼人杀害的玩家。
# 毒药	Poison Potion 或 Poison	用于毒死一名玩家。


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
        self._refresh_witch_inventory_display(witch_entity)

        #
        killed_by_wolf_players = self._game.get_group(
            Matcher(
                all_of=[
                    WolfKillAction,
                    DeathComponent,
                ],
            )
        ).entities.copy()

        if len(killed_by_wolf_players) > 0:
            logger.debug(
                f"被狼人杀害的玩家实体 = {[e.name for e in killed_by_wolf_players]}"
            )
            # 随机选择一个被杀的玩家进行救治
            kill_player = random.choice(list(killed_by_wolf_players))
            if self._revive_target(witch_entity, kill_player, SDWitchItemName.CURE):
                # 移除解药
                self._remove_potion(witch_entity, SDWitchItemName.CURE)

        # 使用毒药
        alive_town_entities = self._game.get_group(
            Matcher(
                any_of=[
                    WerewolfComponent,
                    SeerComponent,
                    VillagerComponent,
                ],
                none_of=[DeathComponent, WitchCureAction],
            )
        ).entities.copy()

        if len(alive_town_entities) > 0:
            logger.debug(
                f"当前存活的村民实体 = {[e.name for e in alive_town_entities]}"
            )
            # 随机选择一个存活的玩家进行毒杀
            poison_player = random.choice(list(alive_town_entities))
            if self._poison_target(witch_entity, poison_player, SDWitchItemName.POISON):
                # 移除毒药
                self._remove_potion(witch_entity, SDWitchItemName.POISON)

        # 最后测试一下
        self._test()

    ################################################################################################################################################
    # 更新道具的信息
    def _refresh_witch_inventory_display(self, witch_entity: Entity) -> None:

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
    # 对。。。使用毒药
    def _poison_target(
        self,
        witch_entity: Entity,
        target_entity: Entity,
        item_name: str,
    ) -> bool:

        poison_item = self._has_potion(witch_entity, item_name)
        if poison_item is None:
            logger.warning(f"女巫 {witch_entity.name} 没有毒药，无法使用毒药")
            return False

        logger.info(f"女巫 {witch_entity.name} 对 {target_entity.name} 使用了毒药")

        # 记录使用毒药的动作
        target_entity.replace(WitchPoisonAction, target_entity.name, witch_entity.name)
        target_entity.replace(DeathComponent, target_entity.name)

        return True

    ###############################################################################################################################################
    # 对。。。使用解药
    def _revive_target(
        self,
        witch_entity: Entity,
        target_entity: Entity,
        item_name: str,
    ) -> bool:

        cure_item = self._has_potion(witch_entity, item_name)
        if cure_item is None:
            logger.warning(f"女巫 {witch_entity.name} 没有解药，无法使用解药")
            return False

        logger.debug(f"女巫 {witch_entity.name} 对 {target_entity.name} 使用了解药")

        if target_entity.has(WolfKillAction) and target_entity.has(DeathComponent):

            # 移除被狼人杀害的状态
            target_entity.remove(WolfKillAction)
            target_entity.remove(DeathComponent)
            logger.info(
                f"女巫 {witch_entity.name} 使用了解药，救活了玩家 {target_entity.name}"
            )

            # 记录使用解药的动作
            target_entity.replace(
                WitchCureAction, target_entity.name, witch_entity.name
            )

        return True

    ###############################################################################################################################################
    def _has_potion(self, from_entity: Entity, item_name: str) -> Item | None:
        assert from_entity.has(InventoryComponent)
        inventory_component = from_entity.get(InventoryComponent)
        assert inventory_component is not None

        for item in inventory_component.items:
            if item.name == item_name:
                return item
        return None

    ###############################################################################################################################################
    def _remove_potion(self, from_entity: Entity, item_name: str) -> bool:
        assert from_entity.has(InventoryComponent)
        inventory_component = from_entity.get(InventoryComponent)
        assert inventory_component is not None

        for item in inventory_component.items:
            if item.name == item_name:
                inventory_component.items.remove(item)
                return True
        return False

    ###############################################################################################################################################
    def _test(self) -> None:
        test_entities1 = self._game.get_group(
            Matcher(
                all_of=[
                    WitchCureAction,
                ],
            )
        ).entities.copy()

        for test_entity in test_entities1:
            assert not test_entity.has(
                DeathComponent
            ), f"被女巫救活的玩家 {test_entity.name} 不应该有死亡状态"
            assert not test_entity.has(
                WolfKillAction
            ), f"被女巫救活的玩家 {test_entity.name} 不应该有被狼人杀害状态"

        test_entities2 = self._game.get_group(
            Matcher(
                all_of=[
                    WitchPoisonAction,
                ],
            )
        ).entities.copy()

        for test_entity in test_entities2:
            assert test_entity.has(
                DeathComponent
            ), f"被女巫毒死的玩家 {test_entity.name} 应该有死亡状态"
            assert not test_entity.has(
                WolfKillAction
            ), f"被女巫毒死的玩家 {test_entity.name} 不应该有被狼人杀害状态"

    ###############################################################################################################################################
