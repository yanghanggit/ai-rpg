"""穿上时装动作系统模块。"""

from typing import final, override, Dict, List, Final
from loguru import logger
from ..deepseek import DeepSeekClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..models import (
    WearCostumeAction,
    AppearanceComponent,
    AppearanceUpdateEvent,
    WornCostumeComponent,
    StorageComponent,
)
from ..models.items import CostumeItem
from .appearance_prompt_builders import (
    build_appearance_synthesis_prompt,
    build_wear_costume_message,
)


@final
class WearCostumeActionSystem(ReactiveProcessor):

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(WearCostumeAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(WearCostumeAction, AppearanceComponent)

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:

        # 处理每个触发穿装动作的实体
        for entity in entities:
            await self._process_wear_costume(entity)

    ####################################################################################################################################
    async def _process_wear_costume(self, entity: Entity) -> None:
        """穿装入口：依据当前是否已穿戴时装，分派到语义明确的两条路径——
        「从无到穿上」（首次穿装）或「从有到更换」（换装）。"""

        if entity.has(WornCostumeComponent):
            await self._wear_by_swapping_costume(entity)
        else:
            await self._wear_from_no_costume(entity)

    ####################################################################################################################################
    async def _wear_from_no_costume(self, entity: Entity) -> None:
        """从无到穿上：角色当前未穿戴任何时装，直接从全局储物箱取出新时装穿上。"""
        await self._mount_new_costume_and_synthesize_appearance(entity)

    ####################################################################################################################################
    async def _wear_by_swapping_costume(self, entity: Entity) -> None:
        """从有到更换：角色已穿戴其他时装，先取下旧时装归还储物箱（不重置外观、不广播，
        避免出现一次多余的"已脱下"中间态事件），再穿上新时装。"""
        self._return_currently_worn_costume_to_storage(entity)
        await self._mount_new_costume_and_synthesize_appearance(entity)

    ####################################################################################################################################
    def _return_currently_worn_costume_to_storage(self, entity: Entity) -> None:
        """换装专用的状态转移：仅将当前穿戴的时装归还全局储物箱，不涉及外观重置与事件
        广播——外观与广播统一由随后穿上新时装的流程处理，避免重复。"""

        old_costume: CostumeItem = entity.get(WornCostumeComponent).item
        entity.remove(WornCostumeComponent)

        storage_entity = self._game.get_storage_entity()
        assert storage_entity is not None, "找不到全局储物箱实体"
        assert storage_entity.has(
            StorageComponent
        ), "全局储物箱实体缺少 StorageComponent"
        storage_entity.get(StorageComponent).items.append(old_costume)
        logger.debug(
            f"角色 {entity.name} 换装：已将旧时装 {old_costume.name!r} 归还储物箱"
        )

    ####################################################################################################################################
    async def _mount_new_costume_and_synthesize_appearance(
        self, entity: Entity
    ) -> None:
        """穿装核心：从全局 StorageComponent 移除新时装、挂载 WornCostumeComponent，
        LLM 合成外观描述并广播。供「从无到穿上」与「从有到更换」两条路径共用。"""

        action = entity.get(WearCostumeAction)
        costume = action.costume_item

        # 修改全局储物箱，移除待穿戴的时装
        storage_entity = self._game.get_storage_entity()
        assert storage_entity is not None, "找不到全局储物箱实体"
        assert storage_entity.has(
            StorageComponent
        ), "全局储物箱实体缺少 StorageComponent"
        storage = storage_entity.get(StorageComponent)
        storage.items[:] = [
            item for item in storage.items if item.name != action.costume_item_name
        ]

        # 挂载 WornCostumeComponent
        entity.replace(WornCostumeComponent, entity.name, costume)

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

        try:
            # 发送请求并等待响应
            await client.chat()

        except Exception as e:

            logger.error(f"LLM 外观合成请求失败，角色 {entity.name}，错误: {e}")
            return

        # 将 LLM 响应应用回对应角色的外观组件
        new_appearance = client.response_content.strip()
        logger.debug(f"LLM 外观合成返回: {new_appearance}")

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
