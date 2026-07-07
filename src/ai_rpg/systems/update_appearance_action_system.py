"""外观更新动作系统模块。"""

from typing import final, override, Dict, List, Final
from loguru import logger
from ..deepseek import DeepSeekClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
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

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

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

        # 无论穿还是脱，先执行脱装（有时装则归还储物箱并重置外观）
        self._process_remove_costume(entity)

        # 有新时装时再执行穿装
        if action.costume_item_name:
            await self._process_wear_costume(entity)

    ####################################################################################################################################
    def _process_remove_costume(
        self,
        entity: Entity,
    ) -> None:
        """脱装：取出 CostumeComponent.item，移除组件，归还全局 StorageComponent，重置外观。无时装时静默跳过。"""

        if not entity.has(CostumeComponent):
            return

        costume_item: CostumeItem = entity.get(CostumeComponent).item
        entity.remove(CostumeComponent)

        # 归还全局储物箱
        storage_entity = self._game.get_storage_entity()
        assert storage_entity is not None, "找不到全局储物箱实体"
        assert storage_entity.has(
            StorageComponent
        ), "全局储物箱实体缺少 StorageComponent"
        storage_entity.get(StorageComponent).items.append(costume_item)

        appearance_comp = entity.get(AppearanceComponent)
        # 重置外观为基础体型
        entity.replace(
            AppearanceComponent,
            appearance_comp.name,
            appearance_comp.base_body,
            appearance_comp.base_body,
        )
        logger.debug(
            f"角色 {entity.name} 已移除时装 {costume_item.name!r}，外观重置为基础体型"
        )

        # 广播外观更新事件，通知前端或其他系统角色外观已恢复为基础体型
        stage_entity = self._game.resolve_stage_entity(entity)
        assert stage_entity is not None, "actor无所在场景是有问题的"
        self._game.broadcast_to_stage(
            entity,
            AppearanceUpdateEvent(
                message=build_remove_costume_message(
                    entity.name, appearance_comp.base_body
                ),
                actor=entity.name,
                stage=stage_entity.name,
                appearance=appearance_comp.base_body,
            ),
        )

    ####################################################################################################################################
    async def _process_wear_costume(
        self,
        entity: Entity,
    ) -> None:
        """穿装：直接使用 action.costume_item，从 StorageComponent 移除，挂载组件，LLM 合成外观描述。"""

        action = entity.get(UpdateAppearanceAction)
        costume = action.costume_item
        if costume is None:
            logger.warning(
                f"外观更新失败: action.costume_item 为空，角色 {entity.name}"
            )
            return

        # 修改全局储物箱，移除已穿戴的时装
        storage_entity = self._game.get_storage_entity()
        assert storage_entity is not None, "找不到全局储物箱实体"
        assert storage_entity.has(
            StorageComponent
        ), "全局储物箱实体缺少 StorageComponent"
        storage = storage_entity.get(StorageComponent)
        storage.items[:] = [
            item for item in storage.items if item.name != action.costume_item_name
        ]

        # 挂载 CostumeComponent
        entity.replace(CostumeComponent, entity.name, costume)

        # 使用 LLM 合成外观描述
        appearance_comp = entity.get(AppearanceComponent)
        prompt = build_appearance_synthesis_prompt(
            base_body=appearance_comp.base_body,
            costume_name=costume.name,
            costume_description=costume.description,
        )

        # 创建 DeepSeekClient 并发送请求
        client = DeepSeekClient(
            name=entity.name,
            prompt=prompt,
            context=self._game.get_agent_context(entity).context,
        )

        # 发送请求并等待响应
        await client.chat()

        # 将 LLM 响应应用回对应角色的外观组件
        new_appearance = client.response_content.strip()

        # 如果 LLM 返回空字符串，则退回 base_body + costume.description 的拼接
        if not new_appearance:
            logger.warning(f"LLM 外观合成返回空响应，角色 {entity.name} 退回简单拼接")
            new_appearance = f"{appearance_comp.base_body}，{costume.description}"

        # 更新外观组件
        entity.replace(
            AppearanceComponent,
            appearance_comp.name,
            appearance_comp.base_body,
            new_appearance,
        )
        logger.debug(f"角色 {entity.name} 外观已更新，当前时装: {costume.name!r}")

        # 广播外观更新事件，通知前端或其他系统角色外观已更新
        stage_entity = self._game.resolve_stage_entity(entity)
        assert stage_entity is not None, "actor无所在场景是有问题的"
        self._game.broadcast_to_stage(
            entity,
            AppearanceUpdateEvent(
                message=build_wear_costume_message(
                    entity.name, costume.name, new_appearance
                ),
                actor=entity.name,
                stage=stage_entity.name,
                appearance=new_appearance,
            ),
        )
