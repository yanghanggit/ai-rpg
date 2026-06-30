"""外观更新动作系统模块。"""

from typing import final, override, Dict, List
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
from ..models.items import CostumeItem
from .appearance_prompt_builders import (
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
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(UpdateAppearanceAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(UpdateAppearanceAction, AppearanceComponent)

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:

        # 处理每个触发外观更新动作的实体
        for entity in entities:
            await self._process_update_appearance_action(entity)

    ####################################################################################################################################
    async def _process_update_appearance_action(self, entity: Entity) -> None:
        """处理外观更新动作：先脱（若有），costume_item_name 非空则再穿上新时装。"""

        action = entity.get(UpdateAppearanceAction)
        appearance_comp = entity.get(AppearanceComponent)

        # 纯脱装请求但无时装：断言失败
        assert action.costume_item_name or entity.has(
            CostumeComponent
        ), f"角色 {entity.name} 未穿戴时装，脱装请求忽略"

        # 无论穿还是脱，先执行脱装（有时装则归还储物箱并重置外观）
        self._process_remove_costume(entity, appearance_comp)

        # 有新时装时再执行穿装
        if action.costume_item_name:
            await self._process_wear_costume(entity, action, appearance_comp)

    ####################################################################################################################################
    def _process_remove_costume(
        self,
        entity: Entity,
        appearance_comp: AppearanceComponent,
    ) -> None:
        """脱装：取出 CostumeComponent.item，移除组件，归还全局 StorageComponent，重置外观。无时装时静默跳过。"""

        if not entity.has(CostumeComponent):
            return

        costume_item: CostumeItem = entity.get(CostumeComponent).item
        entity.remove(CostumeComponent)

        storage_entity = self._game.get_storage_entity()
        assert storage_entity is not None, "找不到全局储物箱实体"
        assert storage_entity.has(
            StorageComponent
        ), "全局储物箱实体缺少 StorageComponent"
        storage_entity.get(StorageComponent).items.append(costume_item)

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

    ####################################################################################################################################
    async def _process_wear_costume(
        self,
        entity: Entity,
        action: UpdateAppearanceAction,
        appearance_comp: AppearanceComponent,
    ) -> None:
        """穿装：直接使用 action.costume_item，从 StorageComponent 移除，挂载组件，LLM 合成外观描述。"""

        costume = action.costume_item
        if costume is None:
            logger.warning(
                f"外观更新失败: action.costume_item 为空，角色 {entity.name}"
            )
            return

        storage_entity = self._game.get_storage_entity()
        assert storage_entity is not None, "找不到全局储物箱实体"
        assert storage_entity.has(
            StorageComponent
        ), "全局储物箱实体缺少 StorageComponent"
        storage = storage_entity.get(StorageComponent)
        storage.items[:] = [
            item for item in storage.items if item.name != action.costume_item_name
        ]

        entity.replace(CostumeComponent, entity.name, costume)

        prompt = build_appearance_synthesis_prompt(
            base_body=appearance_comp.base_body,
            costume_name=costume.name,
            costume_description=costume.description,
        )
        client = DeepSeekClient(
            name=entity.name,
            prompt=prompt,
            context=self._game.get_agent_context(entity).context,
        )
        await client.chat()
        new_appearance = client.response_content.strip()

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
