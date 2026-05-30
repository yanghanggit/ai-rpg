"""外观更新动作系统模块。

处理玩家在家园场景中装备或移除时装（CostumeItem）的动作。
- 指定时装名：从玩家 StorageComponent 取出时装 → 挂载 CostumeComponent，调用 LLM 语义合成最终外观描述，广播给场景内所有角色。
- 空字符串：移除 CostumeComponent，将时装归还玩家 StorageComponent，将 appearance 重置为 base_body，广播给场景内所有角色。
"""

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


def _build_appearance_synthesis_prompt(
    base_body: str,
    costume_name: str,
    costume_description: str,
) -> str:
    """构建外观合成提示词。"""
    return f"""\
你刚刚穿上了时装「{costume_name}」。

基础体型：{base_body}
时装「{costume_name}」描述：{costume_description}

时装会覆盖或遮挡身体部分特征（如面具遮脸、上衣覆盖上身、裙子遮住腿部），请综合推理穿戴后的真实视觉效果，用第三人称写一段简短的外观描述（不超过50字）。只输出外观描述本身，不要解释。\
"""


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
        for entity in entities:
            await self._process_update_appearance_action(entity)

    ####################################################################################################################################
    async def _process_update_appearance_action(self, entity: Entity) -> None:
        """处理外观更新动作：空 item_name 脱装，否则从玩家 StorageComponent 取出时装穿上。"""

        action = entity.get(UpdateAppearanceAction)
        appearance_comp = entity.get(AppearanceComponent)

        # 空字符串：脱装 —— 取出 CostumeComponent.item，移除组件，归还玩家 StorageComponent，重置外观
        if not action.item_name:
            if not entity.has(CostumeComponent):
                logger.warning(f"角色 {entity.name} 未穿戴时装，脱装请求忽略")
                return

            costume_item: CostumeItem = entity.get(CostumeComponent).item
            entity.remove(CostumeComponent)

            player_entity = self._game.get_player_entity()
            assert player_entity is not None, "找不到玩家实体"
            assert player_entity.has(StorageComponent), "玩家实体缺少 StorageComponent"
            storage = player_entity.get(StorageComponent)
            player_entity.replace(
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
                    message=f"# {entity.name} 的外观已更新\n时装已移除，外观恢复为基础体型。\n当前外观：{appearance_comp.base_body}",
                    actor="",
                    target=entity.name,
                    appearance=appearance_comp.base_body,
                ),
            )
            return

        # 穿装 —— 时装来源始终是玩家的 StorageComponent
        player_entity = self._game.get_player_entity()
        assert player_entity is not None, "找不到玩家实体"
        assert player_entity.has(StorageComponent), "玩家实体缺少 StorageComponent"
        storage = player_entity.get(StorageComponent)
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
        player_entity.replace(
            StorageComponent,
            storage.name,
            [item for item in storage.items if item.name != action.item_name],
        )

        # 挂载 CostumeComponent
        entity.replace(CostumeComponent, entity.name, costume)

        # LLM 语义合成外观描述
        prompt = _build_appearance_synthesis_prompt(
            base_body=appearance_comp.base_body,
            costume_name=costume.name,
            costume_description=costume.description,
        )
        client = DeepSeekClient(
            name=entity.name,
            prompt=prompt,
            context=self._game.get_agent_context(entity).context,
        )
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
                message=f"# {entity.name} 的外观已更新\n{entity.name} 穿上了「{costume.name}」。\n当前外观：{new_appearance}",
                actor="",
                target=entity.name,
                appearance=new_appearance,
            ),
        )
