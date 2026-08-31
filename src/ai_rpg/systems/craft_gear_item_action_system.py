"""工坊合成装备系统模块。"""

from typing import Dict, Final, List, Optional, final

from loguru import logger
from overrides import override
from pydantic import BaseModel

from ..deepseek import DeepSeekClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..models import (
    BUILD_CARD_FIELD_DESCRIPTION,
    Card,
    CraftGearItemAction,
    StorageComponent,
    TargetType,
)
from ..models.items import AnyItem, GearItem, ItemType, MaterialItem
from ..utils import extract_json, prompt_builder


#######################################################################################################################################
@final
class _CraftCardSpec(BaseModel):
    """工坊合成装备时 LLM 生成的卡牌功能规格（name/description 由装备名与描述沿用）。"""

    on_play_affixes: List[str] = []
    on_hit_affixes: List[str] = []
    on_turn_end_affixes: List[str] = []
    playable: bool = True
    exhaust: bool = False
    retain: bool = False
    ethereal: bool = False
    transferable: bool = False
    cost: int = 1
    damage: int = 0
    hit_count: int = 1
    block: int = 0
    self_target: bool = False
    target_type: str = TargetType.SINGLE


@final
class _CraftGearItemResponse(BaseModel):
    """工坊合成装备的 LLM 响应数据模型。"""

    name: str = ""
    description: str = ""
    card: _CraftCardSpec


#######################################################################################################################################
@prompt_builder
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

    return f"""# 任务：根据材料创意合成一件装备

## 投入材料

{material_lines}

## 要求

- **name**：装备全名，采用「装备.XXXX」命名格式，体现材料特性与装备类型，简洁有辨识度
- **description**：物品描述，30-60字，说明外观、手感或穿戴感受，体现材料的来源与工艺痕迹
- **card**：这件装备在战斗中被转化为手牌时的完整卡牌规格（对象）；`name`/`description` 由系统沿用装备的 `name`/`description`，因此 `card` 内不要输出 name/description，只输出下列功能字段：
  - `on_play_affixes` / `on_hit_affixes` / `on_turn_end_affixes` / `playable` / `exhaust` / `retain` / `ethereal` / `transferable` / `cost` / `damage` / `hit_count` / `block` / `self_target` / `target_type`
  - 字段含义严格以「卡牌字段说明」为准，未提及即禁止

## 卡牌字段说明

{BUILD_CARD_FIELD_DESCRIPTION}

## 输出格式

```json
{{
  "name": "装备.XXX",
  "description": "...",
  "card": {{
    "on_play_affixes": [],
    "on_hit_affixes": [],
    "on_turn_end_affixes": [],
    "playable": true,
    "exhaust": false,
    "retain": false,
    "ethereal": false,
    "transferable": false,
    "cost": 1,
    "damage": 3,
    "hit_count": 1,
    "block": 0,
    "self_target": false,
    "target_type": "single"
  }}
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
            entity: 携带 CraftGearItemAction 的工坊世界实体
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

        # 由 LLM 产出的卡牌规格构造完整 Card
        card = self._build_card(result)
        if card is None:
            return

        # 更新 StorageComponent：扣减材料 + 追加成品
        new_item = GearItem(
            name=result.name,
            description=result.description,
            resources=action.material_items,
            card=card,
        )
        self._update_storage(storage_entity, action.material_names, new_item)

        logger.info(
            f"[CraftGearItemActionSystem] 合成完成: {new_item.name} "
            f"card={new_item.card}"
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
            full_prompt=prompt,
            messages=self._game.get_agent_memory(entity).messages,
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
            json_str = extract_json(chat_client.response_content)
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
    def _build_card(self, result: _CraftGearItemResponse) -> Optional[Card]:
        """将 LLM 产出的卡牌规格构造为完整 Card；target_type 非法时返回 None。"""
        valid_target_types = {t.value for t in TargetType}
        if result.card.target_type not in valid_target_types:
            logger.error(
                f"[CraftGearItemActionSystem] target_type 无效: {result.card.target_type!r}"
            )
            return None

        return Card(
            name=result.name,
            description=result.description,
            on_play_affixes=result.card.on_play_affixes,
            on_hit_affixes=result.card.on_hit_affixes,
            on_turn_end_affixes=result.card.on_turn_end_affixes,
            playable=result.card.playable,
            exhaust=result.card.exhaust,
            retain=result.card.retain,
            ethereal=result.card.ethereal,
            transferable=result.card.transferable,
            cost=result.card.cost,
            damage=result.card.damage,
            hit_count=result.card.hit_count,
            block=result.card.block,
            self_target=result.card.self_target,
            target_type=TargetType(result.card.target_type),
        )

    ####################################################################################################################################
    def _update_storage(
        self,
        storage_entity: Entity,
        material_names: List[str],
        new_item: GearItem,
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
