"""外观更新动作系统模块。"""

from typing import final, override
from loguru import logger
from ..deepseek import DeepSeekClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    UpdateAppearanceAction,
    AppearanceComponent,
    AppearanceUpdateEvent,
    CostumeComponent,
    StorageComponent,
)
from ..models.items import CostumeItem, ItemType
from .appearance_synthesis_prompt import (
    build_appearance_synthesis_prompt,
    build_remove_costume_message,
    build_wear_costume_message,
)


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
        return entity.has(UpdateAppearanceAction, AppearanceComponent)

    ####################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:

        # 处理每个触发外观更新动作的实体
        for entity in entities:
            await self._process_update_appearance_action(entity)

    ####################################################################################################################################
    async def _process_update_appearance_action(self, entity: Entity) -> None:
        """处理外观更新动作：空 item_name 脱装，否则从玩家 StorageComponent 取出时装穿上。"""

        action = entity.get(UpdateAppearanceAction)
        appearance_comp = entity.get(AppearanceComponent)

        # 空字符串：脱装 —— 取出 CostumeComponent.item，移除组件，归还全局 StorageComponent，重置外观
        if not action.item_name:
            if not entity.has(CostumeComponent):
                logger.warning(f"角色 {entity.name} 未穿戴时装，脱装请求忽略")
                return

            costume_item: CostumeItem = entity.get(CostumeComponent).item
            entity.remove(CostumeComponent)

            storage_entity = self._game.get_storage_entity()
            assert storage_entity is not None, "找不到全局储物箱实体"
            assert storage_entity.has(
                StorageComponent
            ), "全局储物箱实体缺少 StorageComponent"
            storage = storage_entity.get(StorageComponent)
            storage_entity.replace(
                StorageComponent,
                storage.name,
                list(storage.items) + [costume_item],
            )

            entity.replace(
                AppearanceComponent,
                appearance_comp.name,
                appearance_comp.base_body,
                appearance_comp.base_body,
            )
            logger.debug(
                f"角色 {entity.name} 已移除时装 {costume_item.name!r}，外观重置为基础体型"
            )
            self._game.broadcast_to_stage(
                entity,
                AppearanceUpdateEvent(
                    message=build_remove_costume_message(
                        entity.name, appearance_comp.base_body
                    ),
                    actor="",
                    target=entity.name,
                    appearance=appearance_comp.base_body,
                ),
            )
            return

        # 穿装 —— 时装来源始终是全局 StorageComponent
        storage_entity = self._game.get_storage_entity()
        assert storage_entity is not None, "找不到全局储物箱实体"
        assert storage_entity.has(
            StorageComponent
        ), "全局储物箱实体缺少 StorageComponent"
        storage = storage_entity.get(StorageComponent)
        costume = next(
            (
                item
                for item in storage.items
                if item.name == action.item_name and item.type == ItemType.COSTUME_ITEM
            ),
            None,
        )

        if costume is None:
            logger.warning(f"外观更新失败: 玩家储物箱中找不到时装 {action.item_name!r}")
            return

        # 从 StorageComponent 移除该时装
        assert isinstance(costume, CostumeItem)
        storage_entity.replace(
            StorageComponent,
            storage.name,
            [item for item in storage.items if item.name != action.item_name],
        )

        # 挂载 CostumeComponent
        entity.replace(CostumeComponent, entity.name, costume)

        # LLM 语义合成外观描述
        prompt = build_appearance_synthesis_prompt(
            base_body=appearance_comp.base_body,
            costume_name=costume.name,
            costume_description=costume.description,
        )

        # 创建 DeepSeekClient 实例并异步调用 LLM 进行外观描述合成
        client = DeepSeekClient(
            name=entity.name,
            prompt=prompt,
            context=self._game.get_agent_context(entity).context,
        )

        # 异步调用 LLM 进行外观描述合成
        await client.async_chat()
        new_appearance = client.response_content.strip()

        # 兜底：LLM 返回空时退回简单拼接
        if not new_appearance:
            logger.warning(f"LLM 外观合成返回空响应，角色 {entity.name} 退回简单拼接")
            new_appearance = f"{appearance_comp.base_body}，{costume.description}"

        entity.replace(
            AppearanceComponent,
            appearance_comp.name,
            appearance_comp.base_body,
            new_appearance,
        )

        logger.debug(f"角色 {entity.name} 外观已更新，当前时装: {costume.name!r}")
        self._game.broadcast_to_stage(
            entity,
            AppearanceUpdateEvent(
                message=build_wear_costume_message(
                    entity.name, costume.name, new_appearance
                ),
                actor="",
                target=entity.name,
                appearance=new_appearance,
            ),
        )
