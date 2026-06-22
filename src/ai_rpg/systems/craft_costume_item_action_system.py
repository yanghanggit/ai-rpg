"""工坊制作时装系统模块。"""

from typing import Dict, Final, List, final
from loguru import logger
from overrides import override
from pydantic import BaseModel
from ..deepseek import DeepSeekClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    CraftCostumeItemAction,
    StorageComponent,
    WorldComponent,
    WorkshopComponent,
)
from ..models.items import AnyItem, CostumeItem, ItemType, MaterialItem
from ..utils import extract_json_from_code_block


#######################################################################################################################################
@final
class _CraftCostumeItemResponse(BaseModel):
    """工坊制作时装的 LLM 响应数据模型。"""

    name: str = ""
    description: str = ""


#######################################################################################################################################
def _build_craft_costume_prompt(materials: List[MaterialItem]) -> str:
    """构建制作时装的 LLM 提示词。

    Args:
        materials: 参与制作的材料列表（已去重计数）

    Returns:
        完整提示词字符串
    """
    material_lines = "\n".join(
        f"- **{m.name}**（数量 {m.count}）：{m.description}" for m in materials
    )

    return f"""# 任务：根据材料创意制作一件时装

## 投入材料

{material_lines}

## 要求

- **name**：时装全名，采用「时装.XXXX」命名格式，体现材料特性与服饰风格，简洁有辨识度
- **description**：时装描述，30-60字，说明外观、质感或穿着效果，体现材料的来源与工艺痕迹；描述须侧重**穿着后的视觉外观变化**（如颜色、轮廓、装饰细节），而非战斗属性

## 注意

- 时装**不改变任何战斗属性**，仅作为外观道具
- 命名和描述应贴合游戏世界观（沙漠废墟冒险风格）

## 输出格式

```json
{{
  "name": "时装.XXX",
  "description": "..."
}}
```

严格按 JSON 格式输出，不要添加其他内容。"""


#######################################################################################################################################
@final
class CraftCostumeItemActionSystem(ReactiveProcessor):
    """工坊制作时装系统。"""

    def __init__(self, game: TCGGame) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(CraftCostumeItemAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(CraftCostumeItemAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        workshop_entities = self._game.get_group(
            Matcher(all_of=[WorldComponent, WorkshopComponent])
        ).entities.copy()

        if not workshop_entities:
            logger.error(
                "[CraftCostumeItemActionSystem] 未找到工坊世界系统实体，无法执行制作流程"
            )
            return

        assert len(workshop_entities) == 1, "存在多个工坊世界系统实体，数据异常"
        workshop_entity = next(iter(workshop_entities))

        for entity in entities:
            await self._craft(entity, workshop_entity)

    ####################################################################################################################################
    async def _craft(self, entity: Entity, workshop_entity: Entity) -> None:
        """对单个触发实体执行完整制作流程。

        Args:
            entity: 携带 CraftCostumeItemAction 的实体（玩家实体）
            workshop_entity: 持有 WorkshopComponent 的世界系统实体
        """
        action = entity.get(CraftCostumeItemAction)

        storage_entity = self._game.get_storage_entity()
        if storage_entity is None or not storage_entity.has(StorageComponent):
            logger.error(
                "[CraftCostumeItemActionSystem] 全局储物箱实体不存在或缺少 StorageComponent"
            )
            return

        # 材料列表由 activate_craft_costume_item 预填充（count = 本次使用量）
        materials = action.material_items

        # 调用 LLM 生成时装
        result = await self._call_llm(workshop_entity, materials)
        if result is None:
            return

        # 更新 StorageComponent：扣减材料 + 追加成品
        new_item = CostumeItem(
            name=result.name,
            description=result.description,
            craft_materials=action.material_items,
        )
        self._update_storage(storage_entity, action.material_names, new_item)

        logger.info(
            f"[CraftCostumeItemActionSystem] 制作完成: {new_item.name} "
            f"description={new_item.description[:30]}..."
        )

    ####################################################################################################################################
    async def _call_llm(
        self,
        workshop_entity: Entity,
        materials: List[MaterialItem],
    ) -> _CraftCostumeItemResponse | None:
        """调用 WorkshopComponent agent 推理生成时装属性。

        Args:
            workshop_entity: 持有 WorkshopComponent 的世界系统实体
            materials: 合并后的材料列表（count = 本次使用量）

        Returns:
            解析成功的响应对象；解析失败返回 None
        """
        prompt = _build_craft_costume_prompt(materials)
        chat_client = DeepSeekClient(
            name=workshop_entity.name,
            prompt=prompt,
            context=self._game.get_agent_context(workshop_entity).context,
        )
        await chat_client.chat()

        raw = chat_client.response_content
        if not raw:
            logger.error("[CraftCostumeItemActionSystem] LLM 返回空响应")
            return None

        try:
            json_str = extract_json_from_code_block(raw)
            response = _CraftCostumeItemResponse.model_validate_json(json_str)
            assert response.name, "LLM 返回的 name 不能为空"
        except Exception as e:
            logger.error(
                f"[CraftCostumeItemActionSystem] 解析 LLM 响应失败: {e}\n原始内容:\n{raw}"
            )
            return None

        if not response.name:
            logger.error("[CraftCostumeItemActionSystem] LLM 返回的 name 为空")
            return None

        return response

    ####################################################################################################################################
    def _update_storage(
        self,
        storage_entity: Entity,
        material_names: List[str],
        new_item: CostumeItem,
    ) -> None:
        """扣减已用材料（count 递减，归零则移除），追加制作品到 StorageComponent。

        Args:
            storage_entity: 全局储物箱实体
            material_names: action 中记录的材料名称列表（允许重复）
            new_item: 制作成功的 CostumeItem 实例
        """
        storage = storage_entity.get(StorageComponent)

        # 统计需要扣减的数量
        deduct: Dict[str, int] = {}
        for name in material_names:
            deduct[name] = deduct.get(name, 0) + 1

        updated_items: List[AnyItem] = []
        for item in storage.items:
            if item.type == ItemType.MATERIAL_ITEM and item.name in deduct:
                remaining = item.count - deduct[item.name]
                deduct[item.name] = 0  # 单个 item 对象只扣一次
                if remaining > 0:
                    assert isinstance(item, MaterialItem)
                    copied = item.model_copy(deep=True)
                    copied.count = remaining
                    updated_items.append(copied)
                # remaining <= 0：归零，不追加（即从列表移除）
            else:
                updated_items.append(item)

        updated_items.append(new_item)

        storage_entity.replace(StorageComponent, storage.name, updated_items)
