"""工坊合成装备系统模块。"""

from typing import Final, List, Optional, final, Dict
from loguru import logger
from overrides import override
from pydantic import BaseModel
from ..deepseek import DeepSeekClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..models import (
    CraftGearItemAction,
    StorageComponent,
)
from ..models.items import AnyItem, GearItem, ItemType, MaterialItem
from ..models.stats import CharacterStats
from ..models.target_type import TargetType
from ..utils import extract_json_from_code_block


#######################################################################################################################################
@final
class _CraftGearItemResponse(BaseModel):
    """工坊合成装备的 LLM 响应数据模型。"""

    name: str = ""
    description: str = ""
    stat_bonuses: CharacterStats = CharacterStats()
    target_type: TargetType = TargetType.ALLY_SINGLE
    equip_affixes: List[str] = []
    on_hit_affixes: List[str] = []
    modifiers: List[str] = []


#######################################################################################################################################
def _build_craft_gear_prompt(materials: List[MaterialItem]) -> str:
    """构建合成装备的 LLM 提示词。

    Args:
        materials: 参与合成的材料列表（已去重计数）

    Returns:
        完整提示词字符串
    """
    material_lines = "\n".join(
        f"- **{m.name}**（数量 {m.count}）：{m.description}" for m in materials
    )
    target_type_options = "、".join(t.value for t in TargetType)

    return f"""# 任务：根据材料创意合成一件装备

## 投入材料

{material_lines}

## 要求

- **name**：装备全名，采用「装备.XXXX」命名格式，体现材料特性与装备类型，简洁有辨识度
- **description**：物品描述，30-60字，说明外观、手感或穿戴感受，体现材料的来源与工艺痕迹
- **stat_bonuses**：属性加成对象，字段含义如下（所有字段默认为 0，根据装备定位填写合理非零值）：
  - hp：当前生命值加成（通常为 0，一般不改变）
  - max_hp：最大生命值加成（防具类可适当给 5~15）
  - attack：攻击力加成（武器类可给 2~6）
  - defense：防御力加成（防具类可给 2~5）
  - energy：行动次数加成（通常为 0）
  - speed：速度加成（轻型装备或饰品可给 1~2）
- **target_type**：装备作用目标，从以下选项中选一个：{target_type_options}
  - ally_single：作用于单个友方（大多数武器防具默认）
  - self_only：仅作用于自身
- **equip_affixes**：装备时对装备者触发的延迟词缀列表，格式 `[名称]:触发倾向描述`（如 `[皮革韧性]:承受重击时可能激活韧性层，减少下一次伤害`）；无持续效果时输出 []
- **on_hit_affixes**：出牌命中目标时触发的延迟词缀列表，格式同上（如 `[撕裂伤]:命中后可能引发持续流血`）；无命中效果时输出 []
- **modifiers**：即时修正词缀列表，格式 `[名称]:即时修正描述`，直接注入本次仲裁计算（如 `[穿甲]:无视目标防御的一部分`）；无即时修正时输出 []

## 输出格式

```json
{{
  "name": "装备.XXX",
  "description": "...",
  "stat_bonuses": {{"hp": 0, "max_hp": 0, "attack": 3, "defense": 0, "energy": 0, "speed": 0}},
  "target_type": "ally_single",
  "equip_affixes": [],
  "on_hit_affixes": ["[撕裂伤]:命中后可能引发持续流血"],
  "modifiers": ["[穿甲]:无视目标防御的一部分"]
}}
```

严格按 JSON 格式输出，不要添加其他内容。"""


#######################################################################################################################################
@final
class CraftGearItemActionSystem(ReactiveProcessor):
    """工坊合成装备系统。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(CraftGearItemAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(CraftGearItemAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        assert len(entities) == 1, "同时存在多个 CraftGearItemAction，数据异常"
        entity = entities[0]
        await self._craft(entity)

    ####################################################################################################################################
    async def _craft(self, entity: Entity) -> None:
        """执行完整合成流程。

        Args:
            entity: 携带 CraftGearItemAction 的工坊世界系统实体
        """
        action = entity.get(CraftGearItemAction)

        storage_entity = self._game.get_storage_entity()
        if storage_entity is None or not storage_entity.has(StorageComponent):
            logger.error(
                "[CraftGearItemActionSystem] 全局储物箱实体不存在或缺少 StorageComponent"
            )
            return

        # 材料列表由 activate_craft_gear_item 预填充（count = 本次使用量）
        materials = action.material_items

        # 调用 LLM 生成装备
        result = await self._call_llm(entity, materials)
        if result is None:
            return

        # 更新 StorageComponent：扣减材料 + 追加成品
        new_item = GearItem(
            name=result.name,
            description=result.description,
            stat_bonuses=result.stat_bonuses,
            target_type=result.target_type,
            equip_affixes=result.equip_affixes,
            on_hit_affixes=result.on_hit_affixes,
            modifiers=result.modifiers,
            craft_materials=action.material_items,
        )
        self._update_storage(storage_entity, action.material_names, new_item)

        logger.info(
            f"[CraftGearItemActionSystem] 合成完成: {new_item.name} "
            f"(target={new_item.target_type}, stat_bonuses={new_item.stat_bonuses}, "
            f"equip_affixes={new_item.equip_affixes}, on_hit_affixes={new_item.on_hit_affixes}, "
            f"modifiers={new_item.modifiers})"
        )

    ####################################################################################################################################
    async def _call_llm(
        self,
        entity: Entity,
        materials: List[MaterialItem],
    ) -> Optional[_CraftGearItemResponse]:
        """调用工坊 agent 推理生成装备属性。"""

        # 构建 LLM 提示并初始化 DeepSeekClient，用于与 LLM 进行交互
        prompt = _build_craft_gear_prompt(materials)
        chat_client = DeepSeekClient(
            name=entity.name,
            prompt=prompt,
            context=self._game.get_agent_context(entity).context,
        )

        # 发起 LLM 请求，捕获异常以防止整个流程崩溃
        try:
            await chat_client.chat()
        except Exception as e:
            logger.error(f"[CraftGearItemActionSystem] LLM 请求失败: {e}")
            return None

        # 检查 LLM 是否返回了有效的消息对象，如果为空则记录错误并返回 None
        if chat_client.response_ai_message is None:
            logger.error("[CraftGearItemActionSystem] LLM 回复消息为空")
            return None

        # 尝试从 LLM 的回复中提取 JSON 并解析为 _CraftGearItemResponse 对象
        try:
            json_str = extract_json_from_code_block(chat_client.response_content)
            response = _CraftGearItemResponse.model_validate_json(json_str)
            assert response.name, "LLM 返回的 name 不能为空"
        except Exception as e:
            logger.error(
                f"[CraftGearItemActionSystem] 解析 LLM 响应失败: {e}\n原始内容:\n{chat_client.response_content}"
            )
            return None

        # 再次检查解析后的 response 对象的 name 字段是否为空，确保 LLM 返回的内容有效
        if not response.name:
            logger.error("[CraftGearItemActionSystem] LLM 返回的 name 为空")
            return None

        # 返回解析成功的 response 对象，供调用方使用
        return response

    ####################################################################################################################################
    def _update_storage(
        self,
        storage_entity: Entity,
        material_names: List[str],
        new_item: GearItem,
    ) -> None:
        """扣减已用材料（count 递减，归零则移除），追加合成品到 StorageComponent。

        Args:
            storage_entity: 全局储物箱实体
            material_names: action 中记录的材料名称列表（允许重复）
            new_item: 合成成功的 GearItem 实例
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
