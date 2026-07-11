"""工坊合成消耗品系统模块。"""

from typing import Final, List, Optional, final, Dict
from loguru import logger
from overrides import override
from pydantic import BaseModel
from ..deepseek import DeepSeekClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..models import (
    CraftConsumableAction,
    StorageComponent,
)
from ..models.items import AnyItem, ConsumableItem, ItemType, MaterialItem
from ..models.target_type import TargetType
from ..utils import extract_json_from_code_block


#######################################################################################################################################
@final
class _CraftConsumableResponse(BaseModel):
    """工坊合成消耗品的 LLM 响应数据模型。"""

    name: str = ""
    description: str = ""
    target_type: TargetType = TargetType.SELF_ONLY
    affixes: List[str] = []
    modifiers: List[str] = []


#######################################################################################################################################
def _build_craft_prompt(materials: List[MaterialItem]) -> str:
    """构建合成消耗品的 LLM 提示词。

    Args:
        materials: 参与合成的材料列表（已去重计数）

    Returns:
        完整提示词字符串
    """
    material_lines = "\n".join(
        f"- **{m.name}**（数量 {m.count}）：{m.description}" for m in materials
    )
    target_type_options = "、".join(t.value for t in TargetType)

    return f"""# 任务：根据材料创意合成一件消耗品

## 投入材料

{material_lines}

## 要求

- **name**：消耗品全名，采用「消耗品.XXXX」命名格式，体现材料特性与用途，简洁有辨识度
- **description**：物品描述，30-60字，说明外观、气味或使用感受，体现材料的来源与效果想象
- **target_type**：目标类型，从以下选项中选择一个：{target_type_options}
  - self_only：仅作用于自身（恢复、强化自身）
  - ally_single：作用于单个友方（治疗、辅助）
  - ally_all：作用于全体友方
  - enemy_single：作用于单个敌方（伤害、削弱）
  - enemy_all：作用于全体敌方
  - enemy_random_multi：随机多次打击敌方
- **affixes**：延迟词缀列表，格式 `[名称]:触发倾向描述`，使用后独立推理生成持续状态效果（如 `[燃烧]:可能引发持续扣血`）；无持续效果时输出 []
- **modifiers**：即时修正词缀列表，格式 `[名称]:即时修正描述`，直接注入本次仲裁计算（如 `[穿甲]:无视目标防御`）；无即时修正时输出 []

## 输出格式

```json
{{
  "name": "消耗品.XXX",
  "description": "...",
  "target_type": "self_only",
  "affixes": ["[燃烧]:可能引发持续扣血"],
  "modifiers": ["[穿甲]:无视目标防御"]
}}
```

严格按 JSON 格式输出，不要添加其他内容。"""


#######################################################################################################################################
@final
class CraftConsumableActionSystem(ReactiveProcessor):
    """工坊合成消耗品系统。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(CraftConsumableAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(CraftConsumableAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        assert len(entities) == 1, "同时存在多个 CraftConsumableAction，数据异常"
        entity = entities[0]
        await self._craft(entity)

    ####################################################################################################################################
    async def _craft(self, entity: Entity) -> None:
        """执行完整合成流程。

        Args:
            entity: 携带 CraftConsumableAction 的工坊世界系统实体
        """
        action = entity.get(CraftConsumableAction)

        storage_entity = self._game.get_storage_entity()
        assert storage_entity is not None, "storage_entity is None"

        # 材料列表由 activate_craft_consumable 预填充（count = 本次使用量）
        materials = action.material_items

        # 调用 LLM 生成消耗品
        result = await self._call_llm(entity, materials)
        if result is None:
            return

        # 更新 StorageComponent：扣减材料 + 追加成品
        new_item = ConsumableItem(
            name=result.name,
            description=result.description,
            target_type=result.target_type,
            affixes=result.affixes,
            modifiers=result.modifiers,
            craft_materials=action.material_items,
        )

        # 更新储物箱：扣减已用材料（count 递减，归零则移除），追加合成品
        self._update_storage(storage_entity, action.material_names, new_item)
        logger.info(
            f"[CraftConsumableActionSystem] 合成完成: {new_item.name} "
            f"(target={new_item.target_type}, affixes={new_item.affixes}, modifiers={new_item.modifiers})"
        )

    ####################################################################################################################################
    async def _call_llm(
        self,
        entity: Entity,
        materials: List[MaterialItem],
    ) -> Optional[_CraftConsumableResponse]:
        """调用工坊 agent 推理生成消耗品属性。

        Args:
            entity: 携带 CraftConsumableAction 的工坊世界系统实体
            materials: 合并后的材料列表（count = 本次使用量）

        Returns:
            解析成功的响应对象；解析失败返回 None
        """
        prompt = _build_craft_prompt(materials)
        chat_client = DeepSeekClient(
            name=entity.name,
            prompt=prompt,
            context=self._game.get_agent_context(entity).context,
        )

        # 发起 LLM 请求，捕获异常以防止整个流程崩溃
        try:
            await chat_client.chat()
        except Exception as e:
            logger.error(f"[CraftConsumableActionSystem] LLM 请求失败: {e}")
            return None

        # 检查 LLM 的响应是否为空，如果为空则记录错误并返回 None
        if chat_client.response_ai_message is None:
            logger.error("[CraftConsumableActionSystem] LLM 回复消息为空")
            return None

        # 尝试从 LLM 的回复中提取 JSON 并解析为 _CraftConsumableResponse 对象
        try:
            json_str = extract_json_from_code_block(chat_client.response_content)
            response = _CraftConsumableResponse.model_validate_json(json_str)
            # assert response.name, "LLM 返回的 name 不能为空"
        except Exception as e:
            logger.error(
                f"[CraftConsumableActionSystem] 解析 LLM 响应失败: {e}\n原始内容:\n{chat_client.response_content}"
            )
            return None

        # 再次检查解析后的 response 对象的 name 字段是否为空，确保 LLM 返回的内容有效
        if not response.name:
            logger.error("[CraftConsumableActionSystem] LLM 返回的 name 为空")
            return None

        # 返回解析成功的 response 对象，供调用方使用
        return response

    ####################################################################################################################################
    def _update_storage(
        self,
        storage_entity: Entity,
        material_names: List[str],
        new_item: ConsumableItem,
    ) -> None:
        """扣减已用材料（count 递减，归零则移除），追加合成品到 StorageComponent。

        Args:
            storage_entity: 全局储物箱实体
            material_names: action 中记录的材料名称列表（允许重复）
            new_item: 合成成功的 ConsumableItem 实例
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
