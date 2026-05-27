"""制造物品动作处理系统 —— LLM 驱动，根据材料创意推断生成 ConsumableItem。"""

import copy
import uuid
from typing import Final, List, final, override
from loguru import logger
from pydantic import BaseModel
from ..deepseek import DeepSeekClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..models import (
    CraftItemAction,
    InventoryComponent,
    MaterialItem,
    ConsumableItem,
    TargetType,
    WorldComponent,
    WorkshopComponent,
)
from ..game.tcg_game import TCGGame
from ..utils import extract_json_from_code_block


####################################################################################################################################
@final
class _CraftedItemResponse(BaseModel):
    """LLM 制造输出的临时数据模型，用于校验 JSON 响应格式。

    Attributes:
        name: 产出物品名称
        description: 产出物品描述
        target_type: 使用目标类型（见 TargetType 枚举）
        affixes: 效果词缀列表
    """

    name: str = ""
    description: str = ""
    target_type: str = TargetType.SELF_ONLY
    affixes: List[str] = []


####################################################################################################################################
def _build_craft_prompt(material_items: List[MaterialItem]) -> str:
    material_lines = "\n".join(
        f"- **{item.name}**（数量：{item.count}）：{item.description}"
        for item in material_items
    )
    return f"""玩家提交了以下材料，请根据它们的特性与组合方式，推断并生成一件符合当前世界观的消耗品。

## 材料清单

{material_lines}

## 制造原则

- 世界观一致性：产出物必须符合当前世界观
- 材料关联性：效果必须与原材料的特性自然关联，不能凭空捏造
- 创意性：鼓励有趣、意外但合理的合成结果
- 简洁性：名称 2–6 字，描述 60–120 字，效果词缀清晰

## 输出格式

必须严格按以下 JSON 格式输出，不添加任何其他内容：

```json
{{
  "name": "物品名称",
  "description": "物品的感官描述，体现外观、气味、触感等细节。",
  "target_type": "{TargetType.SELF_ONLY}",
  "affixes": ["[效果词缀名]:效果描述"]
}}
```

### target_type 规则

- `{TargetType.SELF_ONLY}`：恢复性、防护性、自身增益类物品
- `{TargetType.ENEMY_SINGLE}`：单体攻击性物品
- `{TargetType.ENEMY_ALL}`：范围控制性物品

### affixes 规则

- 格式固定为 `[词缀名]:简短描述`
- 若无明显特殊效果，返回空数组 `[]`
- 最多填写 2 条词缀"""


####################################################################################################################################
def _build_craft_result_message(
    material_items: List[MaterialItem], new_item: ConsumableItem
) -> str:
    material_summary = "、".join(m.name for m in material_items)
    effects_text = (
        "\n".join(f"  - {e}" for e in new_item.affixes)
        if new_item.affixes
        else "  （无特殊效果）"
    )
    return (
        f"你将 {material_summary} 送入制造工坊，合成了一件消耗品：\n\n"
        f"**{new_item.name}**\n{new_item.description}\n\n效果：\n{effects_text}"
    )


####################################################################################################################################
@final
class CraftItemActionSystem(ReactiveProcessor):
    """LLM 驱动的物品制造系统。

    监听 CraftItemAction 的添加事件，调用 WorkshopComponent 世界系统实体的 LLM context
    生成 ConsumableItem 并写入背包，同时按材料名列表各扣除 1 个。
    由 home_actions.activate_craft_item() 在家园状态下激活。
    """

    def __init__(self, game: TCGGame) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(CraftItemAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(CraftItemAction) and entity.has(InventoryComponent)

    ####################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        ws_entities = self._game.get_group(
            Matcher(all_of=[WorldComponent, WorkshopComponent])
        ).entities.copy()

        if not ws_entities:
            logger.error("[CraftItemActionSystem] 未找到制造工坊世界系统实体")
            return

        assert len(ws_entities) == 1, "存在多个制造工坊系统实体，数据异常"
        ws_entity = next(iter(ws_entities))

        for entity in entities:
            await self._craft_item(entity, ws_entity)

    ####################################################################################################################################
    async def _craft_item(self, entity: Entity, ws_entity: Entity) -> None:
        """执行单次制造流程。

        Args:
            entity: 携带 CraftItemAction 的玩家实体
            ws_entity: 制造工坊世界系统实体
        """
        craft_action = entity.get(CraftItemAction)
        inventory = entity.get(InventoryComponent)

        material_items: List[MaterialItem] = craft_action.materials
        if not material_items:
            logger.warning(
                f"[CraftItemActionSystem] {entity.name} 的 CraftItemAction.materials 为空，跳过"
            )
            return

        logger.info(
            f"[CraftItemActionSystem] {entity.name} 开始制造，材料：{[m.name for m in material_items]}"
        )

        # 调用 LLM
        agent_context = self._game.get_agent_context(ws_entity)
        chat_client = DeepSeekClient(
            name=ws_entity.name,
            prompt=_build_craft_prompt(material_items),
            context=agent_context.context,
        )
        await chat_client.async_chat()
        response_text = chat_client.response_content

        if not response_text:
            logger.error(f"[CraftItemActionSystem] LLM 返回为空，制造失败")
            return

        # 解析 JSON
        json_str = extract_json_from_code_block(response_text)
        try:
            crafted = _CraftedItemResponse.model_validate_json(json_str)
        except Exception as exc:
            logger.error(
                f"[CraftItemActionSystem] JSON 解析失败: {exc}\n原始响应:\n{response_text}"
            )
            return

        if not crafted.name:
            logger.error("[CraftItemActionSystem] 解析到的物品 name 为空，制造失败")
            return

        # 将 target_type 字符串安全转换为枚举
        try:
            target_type = TargetType(crafted.target_type)
        except ValueError:
            logger.warning(
                f"[CraftItemActionSystem] 未知 target_type={crafted.target_type!r}，默认 {TargetType.SELF_ONLY}"
            )
            target_type = TargetType.SELF_ONLY

        # 构建产出 ConsumableItem
        new_item = ConsumableItem(
            name=crafted.name,
            description=crafted.description,
            target_type=target_type,
            affixes=crafted.affixes,
            count=1,
            uuid=str(uuid.uuid4()),
        )

        # 写入背包：深拷贝列表，避免 Pydantic frozen model 问题
        updated_items = copy.deepcopy(inventory.items)
        updated_items.append(new_item)

        # 扣除材料（各 -1，count 归零则移除）
        for mat in material_items:
            for idx, item in enumerate(updated_items):
                if isinstance(item, MaterialItem) and item.name == mat.name:
                    updated_item = item.model_copy(update={"count": item.count - 1})
                    if updated_item.count <= 0:
                        updated_items.pop(idx)
                    else:
                        updated_items[idx] = updated_item
                    break

        entity.replace(InventoryComponent, inventory.name, updated_items)

        logger.info(
            f"[CraftItemActionSystem] 制造完成：{entity.name} 获得「{new_item.name}」\n"
            f"  描述: {new_item.description}\n"
            f"  效果: {new_item.affixes}"
        )

        # 将制造结果写入 actor 的 LLM context，维持叙事一致性
        self._game.add_human_message(
            entity, _build_craft_result_message(material_items, new_item)
        )
