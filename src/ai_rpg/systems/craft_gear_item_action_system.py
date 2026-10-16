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
    AFFIX_DESIGN_SPEC,
    AFFIX_FIELDS,
    BUILD_CARD_FIELD_DESCRIPTION,
    Card,
    ChatMessage,
    CraftGearItemAction,
    NormalizedStrList,
    StorageComponent,
    SystemMessage,
    TargetType,
    append_item_with_stacking,
    deduct_materials,
    validate_affix_slot,
)
from ..models.items import GearItem, MaterialItem
from ..pgsql import get_card_prototype, list_card_prototype_index
from ..utils import prompt_builder

#######################################################################################################################################
# 装备速度修正的生成护栏（工坊提交校验与示例教学共用）。速度可正可负，
# 决定战斗回合行动顺序；装备的 damage/block 走卡牌通道，速度是唯一的装备级被动。
GEAR_SPEED_MIN: Final[int] = -2
GEAR_SPEED_MAX: Final[int] = 3


#######################################################################################################################################
@final
class _CraftGearSpec(BaseModel):
    """submit_gear 提交的完整装备规格：名称/描述 + 速度被动 + 卡牌字段。"""

    name: str = ""
    description: str = ""
    speed: int = 0  # 装备级被动速度修正（可正可负），与 card 字段无关
    on_play_affixes: NormalizedStrList = []
    on_hit_affixes: NormalizedStrList = []
    on_turn_end_affixes: NormalizedStrList = []
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
        description="提交本次合成的装备规格（名称、描述与完整卡牌规格）。校验不通过会返回错误，可按提示修正后重提；全部通过后再调用 finish_gear 结束。",
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
                "speed": {
                    "type": "integer",
                    "description": (
                        "装备级被动速度修正，可正可负：决定战斗回合行动顺序，数值越大越先出手，"
                        f"同速按创建顺序。允许范围 {GEAR_SPEED_MIN}..{GEAR_SPEED_MAX}，默认 0。"
                        "注意：装备的伤害/格挡由 card 承载，speed 是唯一的装备级被动。"
                    ),
                },
                "card": {
                    "type": "object",
                    "description": "该装备在战斗中被转化为手牌时的完整卡牌规格；card 内不包含 name/description（由系统沿用装备的）",
                    "properties": {
                        "on_play_affixes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "maxItems": 3,
                            "description": "即时词缀（多值列表）；本卡被打出时结算，仅本次出牌生效；每个元素是一条完整独立词缀，格式 `[词缀名]:机械结算描述`，禁止拆分或合并；无则 []",
                        },
                        "on_hit_affixes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "maxItems": 3,
                            "description": "受击词缀（多值列表）；持有者被本次出牌命中时触发；每个元素是一条完整独立词缀，禁止拆分或合并；无则 []",
                        },
                        "on_turn_end_affixes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "maxItems": 3,
                            "description": "回合结束词缀（多值列表）；持有者每次 pass turn 结算一次；每个元素是一条完整独立词缀，禁止拆分或合并；无则 []",
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
                            "description": "出牌时额外为每个目标手牌 copy 一份（本体照常结算并进入弃牌/消耗流程）；默认 false。与 self_target 互斥",
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
                            "description": "锁定出牌者自身；true 时无需 targets。与 transferable 互斥",
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
            "required": ["name", "description", "speed", "card"],
        },
    )
)


#######################################################################################################################################
FINISH_GEAR_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="finish_gear",
        description="装备规格已通过 submit_gear 成功提交后调用，结束本次合成。",
        parameters={"type": "object", "properties": {}},
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
            "keywords": item["keywords"],
        }
        for item in list_card_prototype_index(card_type="装备")
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
    if proto.card_type != "装备":
        return f"错误：{example_id!r} 不是装备卡牌原型，可用 id 请通过 list_gear_examples 查询。"
    logger.info(f"[CraftGearItemActionSystem] get_gear_example 执行: {example_id}")
    return json.dumps(
        {
            "id": proto.prototype_id,
            "name": proto.name,
            "summary": proto.summary,
            "keywords": json.loads(proto.keywords_json),
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
    speed: int = 0,
) -> str:
    """处理 submit_gear 工具调用：校验并暂存装备规格。"""
    assert name, "name 不能为空"
    if not (GEAR_SPEED_MIN <= speed <= GEAR_SPEED_MAX):
        return (
            f"错误：speed 必须在 {GEAR_SPEED_MIN}..{GEAR_SPEED_MAX} 之间（当前 {speed}）。"
            "请修正后重新调用 submit_gear。"
        )
    spec = _CraftGearSpec(name=name, description=description, speed=speed, **card)

    # 词缀设计校验：agent 自设计的骨架 + 词缀必须满足词缀格式。
    valid_target_types = {t.value for t in TargetType}
    if spec.target_type not in valid_target_types:
        return f"错误：target_type 无效（{spec.target_type!r}）。请修正后重新提交。"
    if spec.transferable and spec.self_target:
        return (
            "错误：transferable 与 self_target 互斥，不能同时为 true。"
            "self_target 会锁定自身并跳过目标解析，transferable 需要解析出的目标来分发副本，二者语义冲突。"
            "若要「自传递复制」，请把 target_type 设为 single 并选择自身为目标。"
        )
    probe = Card(
        name=spec.name,
        description=spec.description,
        on_play_affixes=spec.on_play_affixes,
        on_hit_affixes=spec.on_hit_affixes,
        on_turn_end_affixes=spec.on_turn_end_affixes,
        playable=spec.playable,
        exhaust=spec.exhaust,
        retain=spec.retain,
        ethereal=spec.ethereal,
        transferable=spec.transferable,
        cost=spec.cost,
        damage=spec.damage,
        hit_count=spec.hit_count,
        block=spec.block,
        self_target=spec.self_target,
        target_type=TargetType(spec.target_type),
    )
    for affix_field in AFFIX_FIELDS:
        for affix in getattr(probe, affix_field):
            result = validate_affix_slot(affix_field, affix, probe)
            if not result.ok:
                return (
                    f"错误：{affix_field} 词缀不合法：{result.reason}。"
                    "请修正后重新调用 submit_gear。"
                )

    results.append(spec)
    logger.info(
        f"[CraftGearItemActionSystem] submit_gear 执行:\n"
        f"  name: {spec.name}\n"
        f"  speed: {spec.speed}\n"
        f"  target_type: {spec.target_type}\n"
        f"  damage: {spec.damage} / block: {spec.block} / cost: {spec.cost}"
    )
    return f"已记录：{spec.name}。确认无误后调用 finish_gear 结束。"


#######################################################################################################################################
def _handle_finish_gear() -> str:
    """处理 finish_gear 工具调用（无参，仅作为终止信号）。"""
    return "已结束本次装备合成。"


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
- **speed**：装备级被动速度修正，整数，可正可负，范围 {GEAR_SPEED_MIN}..{GEAR_SPEED_MAX}，默认 0。
  它决定战斗回合的行动顺序（数值越大越先出手，同速按创建顺序），在装备登记期间累加。
  装备的伤害 / 格挡**只能**通过下方 `card` 表达，`speed` 是唯一的装备级被动。
  叙事取向：轻捷灵便 → 正值；沉重笨拙 → 负值。

## 卡牌规格（card）

`card` 是这件装备在战斗中被转化为手牌时的完整卡牌规格。`card` 内不输出 `name`/`description`（由系统沿用装备的）；其余字段以下方说明为准，未提及即禁止。
每个字段只表达自己的职责，不重复、不互相替代；三类词缀由你自行决定使用哪些时机（可为空）。

{BUILD_CARD_FIELD_DESCRIPTION}

{AFFIX_DESIGN_SPEC}

## 工作流程

1. 准备阶段：调用 `list_gear_examples` 纵览可用装备示例的索引，结合本次投入材料筛选最相关的示例；
2. 精读阶段：如需，调用 `get_gear_example` 获取 1~2 个最相关示例的完整卡牌规格；
3. 提交阶段：综合材料特性与示例参照，调用 `submit_gear` 提交本次合成的装备规格；若返回错误，按提示修正后重新提交；
4. 结束后：`submit_gear` 成功后再调用 `finish_gear` 结束对话。提交时无需在 content 中展开长篇推导，把分析过程浓缩在内心即可。"""


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
                    FINISH_GEAR_TOOL,
                ],
                handlers={
                    LIST_GEAR_EXAMPLES_TOOL.function.name: _handle_list_gear_examples,
                    GET_GEAR_EXAMPLE_TOOL.function.name: _handle_get_gear_example,
                    SUBMIT_GEAR_TOOL.function.name: partial(_handle_submit_gear, specs),
                    FINISH_GEAR_TOOL.function.name: _handle_finish_gear,
                },
                max_rounds=8,
                terminal_tools=[FINISH_GEAR_TOOL],
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
                "[CraftGearItemActionSystem] LLM 结束但未成功提交装备规格，中止"
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

        # 根据 LLM 返回的装备规格构造 Card 对象。
        # 注意：此处不设 source——成品只是存于储物箱的装备模板，真正的持有者 source
        # 由 EquipGearItemActionSystem._materialize_cards 在物化为手牌时回填。
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
            speed=result.speed,
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
        """扣减已用材料（跨同名条目结转、归零移除），并入合成品到 StorageComponent。"""
        storage = storage_entity.get(StorageComponent)

        updated_items = deduct_materials(storage.items, material_names)
        updated_items = append_item_with_stacking(updated_items, new_item)

        storage_entity.replace(StorageComponent, storage.name, updated_items)
