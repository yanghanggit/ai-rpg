"""工坊合成消耗品系统模块。"""

from typing import Dict, Final, List, Optional, final

from loguru import logger
from overrides import override
from pydantic import BaseModel

from ..deepseek import DeepSeekClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..models import (
    CraftConsumableItemAction,
    StorageComponent,
)
from ..models.items import AnyItem, ConsumableItem, ItemType, MaterialItem
from ..utils import extract_json, prompt_builder


#######################################################################################################################################
@final
class _CraftConsumableResponse(BaseModel):
    """工坊合成消耗品的 LLM 响应数据模型。"""

    name: str = ""
    description: str = ""
    on_use_prompt: List[str] = []


#######################################################################################################################################
#######################################################################################################################################
CONSUMABLE_ON_USE_CAPABILITY: Final[
    str
] = """消耗品的「使用效果提示词」会交给战斗结算 agent 执行，该 agent 仅能：
- 读取发起者与目标的 HP/攻击/防御；
- 修改受影响角色的 HP（0 ≤ HP ≤ 最大 HP）；
- 提交战斗日志、演出叙事与场景环境快照。

因此 on_use_prompt 只能描述「对目标（或发起者）造成伤害 / 恢复 HP」这类可被解释的即时效果，并可用感官描写暗示表现方式；
禁止描述状态效果、属性增减、道具增减、跨回合持续效果等战斗结算 agent 无法解释的机制。"""


@prompt_builder
def _build_craft_prompt(materials: List[MaterialItem]) -> str:
    """构建合成消耗品的 LLM 提示词。"""
    material_lines = "\n".join(
        f"- **{m.name}**（数量 {m.count}）：{m.description}" for m in materials
    )
    return f"""# 任务：根据材料创意合成一件消耗品

## 投入材料

{material_lines}

## 要求

- **name**：消耗品全名，采用「消耗品.XXXX」命名格式，体现材料特性与用途，简洁有辨识度
- **description**：物品描述，30-60字，说明外观、气味或使用感受，体现材料的来源与效果想象
- **on_use_prompt**：使用效果提示词，`[字符串]` 列表，当前仅使用第一项（`[0]`）作为整段效果提示；用一句话说清「对谁、造成什么、数值多少」

## on_use_prompt 能力边界

{CONSUMABLE_ON_USE_CAPABILITY}

## 输出格式

```json
{{
  "name": "消耗品.XXX",
  "description": "...",
  "on_use_prompt": ["对目标造成 3 点伤害。"]
}}
```

严格按 JSON 格式输出，不要添加其他内容。"""


#######################################################################################################################################
@final
class CraftConsumableItemActionSystem(ReactiveProcessor):
    """工坊合成消耗品系统。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(CraftConsumableItemAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(CraftConsumableItemAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        assert len(entities) == 1, "同时存在多个 CraftConsumableAction，数据异常"
        entity = entities[0]
        await self._craft(entity)

    ####################################################################################################################################
    async def _craft(self, entity: Entity) -> None:
        """执行完整合成流程。"""
        action = entity.get(CraftConsumableItemAction)

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
            on_use_prompt=result.on_use_prompt,
            resources=action.material_items,
        )

        # 更新储物箱：扣减已用材料（count 递减，归零则移除），追加合成品
        self._update_storage(storage_entity, action.material_names, new_item)
        logger.info(
            f"[CraftConsumableActionSystem] 合成完成: {new_item.name} "
            f"(on_use_prompt={new_item.on_use_prompt})"
        )

    ####################################################################################################################################
    async def _call_llm(
        self,
        entity: Entity,
        materials: List[MaterialItem],
    ) -> Optional[_CraftConsumableResponse]:
        """调用工坊 agent 推理生成消耗品属性。"""
        prompt = _build_craft_prompt(materials)
        chat_client = DeepSeekClient(
            name=entity.name,
            full_prompt=prompt,
            messages=self._game.get_agent_memory(entity).messages,
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
            json_str = extract_json(chat_client.response_content)
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
        """扣减已用材料（count 递减，归零则移除），追加合成品到 StorageComponent。"""
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
