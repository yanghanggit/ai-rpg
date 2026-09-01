"""工坊合成装备系统模块。"""

import json
from functools import partial
from typing import Any, Dict, Final, List, final

from loguru import logger
from overrides import override
from pydantic import BaseModel

from ..deepseek import ToolDefinition, ToolFunction, agent_loop
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..models import (
    BUILD_CARD_FIELD_DESCRIPTION,
    Card,
    ChatMessage,
    CraftGearItemAction,
    StorageComponent,
    SystemMessage,
    TargetType,
)
from ..models.items import AnyItem, GearItem, ItemType, MaterialItem
from ..pgsql import get_card_prototype, list_card_prototype_index
from ..utils import prompt_builder


#######################################################################################################################################
@final
class _CraftGearSpec(BaseModel):
    """submit_gear 提交的完整装备规格：名称/描述 + 卡牌字段。"""

    name: str = ""
    description: str = ""
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


#######################################################################################################################################
LIST_GEAR_EXAMPLES_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="list_gear_examples",
        description="纵览全部可用装备示例的索引（id / 名称 / 一句话定位 / 机制标签），用于在准备阶段建立全局观并结合材料筛选相关示例。",
        parameters={"type": "object", "properties": {}},
    )
)


#######################################################################################################################################
GET_GEAR_EXAMPLE_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="get_gear_example",
        description="按 id 获取某个示例装备的完整卡牌规格（名称 / 描述 / card 全字段），用于在准备阶段精读最相关的示例。",
        parameters={
            "type": "object",
            "properties": {
                "example_id": {
                    "type": "string",
                    "description": "示例 id，必须来自 list_gear_examples 返回的索引（如 gear.offense / gear.defense / gear.contagion）",
                },
            },
            "required": ["example_id"],
        },
    )
)


#######################################################################################################################################
SUBMIT_GEAR_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="submit_gear",
        description="提交本次合成的装备规格（名称、描述与完整卡牌规格）。调用后本次合成结束。",
        parameters={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "装备全名，采用「装备.XXXX」命名格式，体现材料特性与装备类型",
                },
                "description": {
                    "type": "string",
                    "description": "物品描述，30-60字，说明外观、手感或穿戴感受",
                },
                "card": {
                    "type": "object",
                    "description": "该装备在战斗中被转化为手牌时的完整卡牌规格；card 内不包含 name/description（由系统沿用装备的）",
                    "properties": {
                        "on_play_affixes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "即时词缀；本卡被打出时结算，仅本次出牌生效；无则 []",
                        },
                        "on_hit_affixes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "受击词缀；持有者被本次出牌命中时触发；无则 []",
                        },
                        "on_turn_end_affixes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "回合结束词缀；持有者每次 pass turn 结算一次；无则 []",
                        },
                        "playable": {
                            "type": "boolean",
                            "description": "是否可出牌；默认 true",
                        },
                        "exhaust": {
                            "type": "boolean",
                            "description": "出牌后永久消耗；默认 false",
                        },
                        "retain": {
                            "type": "boolean",
                            "description": "回合末保留在手牌；默认 false",
                        },
                        "ethereal": {
                            "type": "boolean",
                            "description": "pass turn 时若仍在手牌则自动消耗；默认 false",
                        },
                        "transferable": {
                            "type": "boolean",
                            "description": "出牌时从源手牌移除本体并复制到目标手牌；默认 false",
                        },
                        "cost": {
                            "type": "integer",
                            "description": "出牌费用（消耗 energy）；默认 1",
                        },
                        "damage": {
                            "type": "integer",
                            "description": "单次伤害；默认 0",
                        },
                        "hit_count": {
                            "type": "integer",
                            "description": "攻击次数，多段各自独立结算；默认 1",
                        },
                        "block": {
                            "type": "integer",
                            "description": "手牌持有期间提供的格挡；默认 0",
                        },
                        "self_target": {
                            "type": "boolean",
                            "description": "锁定出牌者自身；true 时无需 targets",
                        },
                        "target_type": {
                            "type": "string",
                            "enum": ["single", "all", "spread"],
                            "description": "目标类型：single 单体、all 阵营锚点、spread 散射",
                        },
                    },
                    "required": [
                        "on_play_affixes",
                        "on_hit_affixes",
                        "on_turn_end_affixes",
                        "playable",
                        "exhaust",
                        "retain",
                        "ethereal",
                        "transferable",
                        "cost",
                        "damage",
                        "hit_count",
                        "block",
                        "self_target",
                        "target_type",
                    ],
                },
            },
            "required": ["name", "description", "card"],
        },
    )
)


#######################################################################################################################################
def _handle_list_gear_examples() -> str:
    """处理 list_gear_examples 工具调用：返回装备卡牌原型的 index 纵览。"""
    index = [
        {
            "id": item["prototype_id"],
            "name": item["name"],
            "summary": item["summary"],
            "tags": item["tags"],
        }
        for item in list_card_prototype_index(archetype="装备")
    ]
    logger.info(
        f"[CraftGearItemActionSystem] list_gear_examples 执行: 共 {len(index)} 个示例"
    )
    return json.dumps(index, ensure_ascii=False)


#######################################################################################################################################
def _handle_get_gear_example(example_id: str) -> str:
    """处理 get_gear_example 工具调用：按 id 返回完整卡牌原型（含 card 规格）。"""
    try:
        proto = get_card_prototype(example_id)
    except ValueError as e:
        return f"错误：{e}。可用 id 请通过 list_gear_examples 查询。"
    if proto.archetype != "装备":
        return f"错误：{example_id!r} 不是装备卡牌原型，可用 id 请通过 list_gear_examples 查询。"
    logger.info(f"[CraftGearItemActionSystem] get_gear_example 执行: {example_id}")
    return json.dumps(
        {
            "id": proto.prototype_id,
            "name": proto.name,
            "summary": proto.summary,
            "tags": json.loads(proto.tags_json),
            "guide": proto.guide,
            "card": json.loads(proto.card_json),
        },
        ensure_ascii=False,
    )


#######################################################################################################################################
def _handle_submit_gear(
    results: List[_CraftGearSpec],
    name: str,
    description: str,
    card: Dict[str, Any],
) -> str:
    """处理 submit_gear 工具调用：校验并暂存装备规格。"""
    assert name, "name 不能为空"
    spec = _CraftGearSpec(name=name, description=description, **card)
    results.append(spec)
    logger.info(
        f"[CraftGearItemActionSystem] submit_gear 执行:\n"
        f"  name: {spec.name}\n"
        f"  target_type: {spec.target_type}\n"
        f"  damage: {spec.damage} / block: {spec.block} / cost: {spec.cost}"
    )
    return spec.model_dump_json(ensure_ascii=False)


#######################################################################################################################################
@prompt_builder
def _build_craft_gear_prompt(materials: List[MaterialItem]) -> str:
    """构建合成装备的 LLM 提示词。"""
    material_lines = "\n".join(
        f"- **{m.name}**（数量 {m.count}）：{m.description}" for m in materials
    )

    return f"""# 任务：根据材料创意合成一件装备

## 投入材料

{material_lines}

## 装备叙事

- **name**：装备全名，采用「装备.XXXX」命名格式，体现材料特性与装备类型，简洁有辨识度
- **description**：物品描述，30-60字，说明外观、手感或穿戴感受，体现材料的来源与工艺痕迹

## 卡牌规格（card）

`card` 是这件装备在战斗中被转化为手牌时的完整卡牌规格。`card` 内不输出 `name`/`description`（由系统沿用装备的）；其余字段以下方说明为准，未提及即禁止。
每个字段只表达自己的职责，不重复、不互相替代。

{BUILD_CARD_FIELD_DESCRIPTION}

## 工作流程

1. 准备阶段：调用 `list_gear_examples` 纵览可用装备示例的索引，结合本次投入材料筛选最相关的示例；
2. 精读阶段：如需，调用 `get_gear_example` 获取 1~2 个最相关示例的完整卡牌规格；
3. 提交阶段：综合材料特性与示例约束，直接调用 `submit_gear` 提交本次合成的装备规格并结束对话；提交时无需在 content 中展开长篇推导，把分析过程浓缩在内心即可。"""


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

        # 调用工坊 agent（agent_loop 工具调用模式）推理生成装备属性
        prompt = _build_craft_gear_prompt(materials)

        # 上下文隔离：仅取世界实体的首条 SystemMessage 作为「设定」，
        # 传入全新列表（agent_loop 原地追加），结束后不写回宿主实体持久记忆。
        agent_memory = self._game.get_agent_memory(entity)
        assert agent_memory.messages, "工坊世界实体缺少首条 SystemMessage"
        assert isinstance(
            agent_memory.messages[0], SystemMessage
        ), "工坊世界实体 AI 记忆的第一条消息必须是 SystemMessage"
        messages: List[ChatMessage] = [agent_memory.messages[0]]

        specs: List[_CraftGearSpec] = []

        try:
            # 调用 agent_loop 进行装备合成推理：准备阶段读示例 → 精读 → submit_gear 提交
            success = await agent_loop(
                name=entity.name,
                prompt=prompt,
                messages=messages,
                tools=[
                    LIST_GEAR_EXAMPLES_TOOL,
                    GET_GEAR_EXAMPLE_TOOL,
                    SUBMIT_GEAR_TOOL,
                ],
                handlers={
                    "list_gear_examples": _handle_list_gear_examples,
                    "get_gear_example": _handle_get_gear_example,
                    "submit_gear": partial(_handle_submit_gear, specs),
                },
                max_rounds=8,
                terminal_tools=[SUBMIT_GEAR_TOOL],
            )
        except Exception as e:
            logger.error(f"[CraftGearItemActionSystem] agent_loop 异常: {e}")
            return

        # 检查 agent_loop 是否成功返回
        if not success:
            logger.error("[CraftGearItemActionSystem] agent_loop 失败，中止")
            return

        # 检查 LLM 是否返回了有效的装备规格
        if not specs:
            logger.error(
                "[CraftGearItemActionSystem] LLM 已结束但未调用 submit_gear，中止"
            )
            return

        result = specs[0]

        # 由 LLM 产出的卡牌规格构造完整 Card；target_type 非法时中止
        valid_target_types = {t.value for t in TargetType}
        if result.target_type not in valid_target_types:
            logger.error(
                f"[CraftGearItemActionSystem] target_type 无效: {result.target_type!r}"
            )
            return

        # 根据 LLM 返回的装备规格构造 Card 对象
        card = Card(
            name=result.name,
            description=result.description,
            on_play_affixes=result.on_play_affixes,
            on_hit_affixes=result.on_hit_affixes,
            on_turn_end_affixes=result.on_turn_end_affixes,
            playable=result.playable,
            exhaust=result.exhaust,
            retain=result.retain,
            ethereal=result.ethereal,
            transferable=result.transferable,
            cost=result.cost,
            damage=result.damage,
            hit_count=result.hit_count,
            block=result.block,
            self_target=result.self_target,
            target_type=TargetType(result.target_type),
        )

        # 更新 StorageComponent：扣减材料 + 追加成品
        new_item = GearItem(
            name=result.name,
            description=result.description,
            resources=action.material_items,
            cards=[card],
        )
        self._update_storage(storage_entity, action.material_names, new_item)

        logger.info(
            f"[CraftGearItemActionSystem] 合成完成: {new_item.name} "
            f"cards={new_item.cards}"
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
