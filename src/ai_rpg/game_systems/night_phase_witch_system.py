from typing import final, Tuple, List
from overrides import override
from pydantic import BaseModel
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
from ..utils.md_format import format_list_as_markdown_list
from ..chat_services.client import ChatClient
from ..utils import json_format


@final
class WitchDecisionResponse(BaseModel):
    mind_voice: str
    cure_target: str
    poison_target: str


###############################################################################################################################################
@final
class NightPhaseWitchSystem(ExecuteProcessor):

    ###############################################################################################################################################
    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ###############################################################################################################################################
    @override
    async def execute(self) -> None:
        """女巫夜晚行动的主流程"""
        """验证当前是否为夜晚阶段"""
        assert self._game._time_marker % 2 == 1, "时间标记必须是奇数，是夜晚"
        night_number = self._game._time_marker // 2 + 1
        logger.info(f"夜晚 {night_number} 开始")
        logger.info("女巫请睁眼，选择你要救的玩家或毒的玩家")

        witch_entity = self._get_witch()
        if witch_entity is None:
            return

        logger.debug(f"当前女巫实体 = {witch_entity.name}")
        self._refresh_witch_inventory_display(witch_entity)

        killed = self._game.get_group(
            Matcher(
                all_of=[
                    WolfKillAction,
                    # DeathComponent,
                ],
            )
        ).entities.copy()

        all = self._game.get_group(
            Matcher(
                any_of=[
                    WerewolfComponent,
                    SeerComponent,
                    WitchComponent,
                    VillagerComponent,
                ],
            )
        ).entities.copy()

        status_info: List[Tuple[str, str]] = []
        for one in all:
            if one in killed:
                status_info.append((one.name, "被杀害"))
            else:
                status_info.append((one.name, "存活中"))

        logger.info(f"当前玩家状态: {status_info}")

        response_sample = WitchDecisionResponse(
            mind_voice="你内心独白，你的想法已经你为什么要这么决策",
            cure_target="目标的全名 或者 空字符串 表示不救人",
            poison_target="目标的全名 或者 空字符串 表示不毒人",
        )

        prompt = f"""# 指令！作为女巫，你将决定夜晚的行动。

## 当前可选的查看目标:

{format_list_as_markdown_list(status_info)}

## 决策建议

作为女巫，你应该考虑以下因素来决定你的行动：
1. **救人**: 如果有玩家被狼人杀害，你可以选择使用解药救活其中一人。考虑救谁时，可以基于该玩家的角色重要性（如预言家）或游戏策略（如怀疑某人为狼人）。
2. **毒人**: 你也可以选择使用毒药毒杀一名存活的玩家。选择毒谁时，可以基于你对其他玩家的怀疑或游戏策略。
3. **资源管理**: 记住，你只有一瓶解药和一瓶毒药，每种只能使用一次。合理利用这些资源是关键。
4. **游戏局势**: 考虑当前的游戏局势和其他玩家的行为，做出最有利于你阵营的决策。

## 输出格式

### 标准示例

```json
{response_sample.model_dump_json()}
```

## 输出要求

请严格按照上述的 JSON 标准示例 格式输出！你必须从上述可选目标中选择一个作为target_name。 如果你决定不救人或不毒人，请将对应的字段填写为空字符串。"""

        agent_short_term_memory = self._game.get_agent_chat_history(witch_entity)
        request_handler = ChatClient(
            name=witch_entity.name,
            prompt=prompt,
            chat_history=agent_short_term_memory.chat_history,
        )

        # 执行请求
        await ChatClient.gather_request_post(clients=[request_handler])

        try:
            response = WitchDecisionResponse.model_validate_json(
                json_format.strip_json_code_block(request_handler.response_content)
            )

            if response.mind_voice != "":
                self._game.append_human_message(
                    witch_entity,
                    f"""# 提示！你内心独白: {response.mind_voice}""",
                )

            # 是否救人？
            if response.cure_target != "":

                cure_target_entity = self._game.get_actor_entity(response.cure_target)

                if cure_target_entity is None:
                    logger.error(
                        f"女巫 {witch_entity.name} 想要救的玩家 {response.cure_target} 不存在，跳过救人"
                    )
                else:
                    if self._revive_target(
                        witch_entity, cure_target_entity, SDWitchItemName.CURE
                    ):
                        self._remove_potion(witch_entity, SDWitchItemName.CURE)

                    else:
                        logger.error(
                            f"女巫 {witch_entity.name} 想要救的玩家 {response.cure_target} 失败，跳过救人"
                        )

            # 是否毒人？
            if response.poison_target != "":

                poison_target_entity = self._game.get_actor_entity(
                    response.poison_target
                )

                if poison_target_entity is None:
                    logger.error(
                        f"女巫 {witch_entity.name} 想要毒的玩家 {response.poison_target} 不存在，跳过毒人"
                    )
                else:
                    if self._poison_target(
                        witch_entity, poison_target_entity, SDWitchItemName.POISON
                    ):
                        self._remove_potion(witch_entity, SDWitchItemName.POISON)
                    else:
                        logger.error(
                            f"女巫 {witch_entity.name} 想要毒的玩家 {response.poison_target} 失败，跳过毒人"
                        )

            # 最终什么都不做？
            if response.cure_target == "" and response.poison_target == "":
                self._game.append_human_message(
                    witch_entity,
                    f"""# 提示！你决定本轮不使用任何道具，跳过女巫行动。""",
                )

        except Exception as e:
            logger.error(f"Exception: {e}")
            self._game.append_human_message(
                witch_entity,
                f"""# 提示！在解析你的决策时出现错误。本轮你将跳过女巫行动。""",
            )

        # 验证行动结果
        self._test()

    ################################################################################################################################################
    def _get_witch(self) -> Entity | None:
        """查找存活的女巫实体"""
        alive_witches = self._game.get_group(
            Matcher(
                all_of=[WitchComponent],
                none_of=[DeathComponent],
            )
        ).entities.copy()

        if len(alive_witches) == 0:
            logger.warning("当前没有存活的女巫，无法进行女巫行动")
            return None

        assert len(alive_witches) == 1, "女巫不可能有多个"
        witch_entity = next(iter(alive_witches))
        return witch_entity

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
            self._game.append_human_message(
                witch_entity,
                f"""# 提示！你没有毒药，无法对 {target_entity.name} 使用毒药。""",
            )
            return False

        logger.info(f"女巫 {witch_entity.name} 对 {target_entity.name} 使用了毒药")

        # 记录使用毒药的动作
        target_entity.replace(WitchPoisonAction, target_entity.name, witch_entity.name)
        # target_entity.replace(DeathComponent, target_entity.name)

        self._game.append_human_message(
            witch_entity,
            f"""# 提示！你使用了毒药，成功毒死了玩家 {target_entity.name} 。""",
        )

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
            self._game.append_human_message(
                witch_entity,
                f"""# 提示！你没有解药，无法对 {target_entity.name} 使用解药。""",
            )
            return False

        logger.debug(f"女巫 {witch_entity.name} 对 {target_entity.name} 使用了解药")

        if target_entity.has(WolfKillAction):

            # 移除被狼人杀害的状态
            target_entity.remove(WolfKillAction)
            logger.info(
                f"女巫 {witch_entity.name} 使用了解药，救活了玩家 {target_entity.name}"
            )

            # 记录使用解药的动作
            target_entity.replace(
                WitchCureAction, target_entity.name, witch_entity.name
            )

            # 给女巫一个提示
            self._game.append_human_message(
                witch_entity,
                f"""# 提示！你使用了解药，成功救活了玩家 {target_entity.name} 。""",
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
                self._game.append_human_message(
                    from_entity,
                    f"""# 提示！ {item.name} 被移除了！""",
                )
                return True
        return False

    ###############################################################################################################################################
    def _test(self) -> None:
        pass
        # test_entities1 = self._game.get_group(
        #     Matcher(
        #         all_of=[
        #             WitchCureAction,
        #         ],
        #     )
        # ).entities.copy()

        # for test_entity in test_entities1:
        #     assert not test_entity.has(
        #         DeathComponent
        #     ), f"被女巫救活的玩家 {test_entity.name} 不应该有死亡状态"
        #     assert not test_entity.has(
        #         WolfKillAction
        #     ), f"被女巫救活的玩家 {test_entity.name} 不应该有被狼人杀害状态"

        # test_entities2 = self._game.get_group(
        #     Matcher(
        #         all_of=[
        #             WitchPoisonAction,
        #         ],
        #     )
        # ).entities.copy()

        # for test_entity in test_entities2:
        #     assert test_entity.has(
        #         DeathComponent
        #     ), f"被女巫毒死的玩家 {test_entity.name} 应该有死亡状态"
        #     assert not test_entity.has(
        #         WolfKillAction
        #     ), f"被女巫毒死的玩家 {test_entity.name} 不应该有被狼人杀害状态"

    ###############################################################################################################################################
