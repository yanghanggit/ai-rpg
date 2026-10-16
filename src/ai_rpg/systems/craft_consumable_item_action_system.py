"""工坊合成消耗品系统模块。

向 CraftGearItemActionSystem 看齐：以 agent_loop 工具调用模式让消耗品工坊 agent
「读示例 → 精读 → 提交卡牌规格」，产出一件携带内置伤害卡牌的消耗品。
消耗品卡固定 0 费、一次性（exhaust=True），战斗中使用时物化为手牌后走普通出牌逻辑。
"""

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
    BUILD_CARD_FIELD_DESCRIPTION,
    Card,
    ChatMessage,
    ConsumableItem,
    CraftConsumableItemAction,
    NormalizedStrList,
    StorageComponent,
    SystemMessage,
    TargetType,
    append_item_with_stacking,
    deduct_materials,
    validate_affix_slot,
)
from ..models.items import MaterialItem
from ..pgsql import get_card_prototype, list_card_prototype_index
from ..utils import prompt_builder

#######################################################################################################################################
# 消耗品卡护栏：0 费、一次性、纯伤害（本阶段只做伤害型）。
CONSUMABLE_DAMAGE_MIN: Final[int] = 1
CONSUMABLE_DAMAGE_MAX: Final[int] = 8
CONSUMABLE_HIT_COUNT_MAX: Final[int] = 3

# 消耗品本阶段只做伤害，目标类型白名单显式排除 self（不做自我治疗/自伤）。
CONSUMABLE_TARGET_TYPES: Final[frozenset[str]] = frozenset(
    {TargetType.SINGLE.value, TargetType.ALL.value, TargetType.SPREAD.value}
)


#######################################################################################################################################
@final
class _CraftConsumableSpec(BaseModel):
    """submit_consumable 提交的消耗品规格：叙事身份 + 内置伤害卡的核心字段。"""

    name: str = ""
    description: str = ""
    on_play_affixes: NormalizedStrList = []
    damage: int = 0
    hit_count: int = 1
    target_type: str = TargetType.SINGLE


#######################################################################################################################################
LIST_CONSUMABLE_EXAMPLES_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="list_consumable_examples",
        description="纵览全部可用消耗品卡牌示例的索引（id / 名称 / 一句话定位 / 机制标签），用于在准备阶段建立全局观并结合材料筛选相关示例。",
        parameters={"type": "object", "properties": {}},
    )
)


#######################################################################################################################################
GET_CONSUMABLE_EXAMPLE_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="get_consumable_example",
        description="按 id 获取某个示例消耗品的完整卡牌规格（名称 / 描述 / card 全字段），用于在准备阶段精读最相关的示例。",
        parameters={
            "type": "object",
            "properties": {
                "example_id": {
                    "type": "string",
                    "description": "示例 id，必须来自 list_consumable_examples 返回的索引（如 consumable.single / consumable.aoe / consumable.spread）",
                },
            },
            "required": ["example_id"],
        },
    )
)


#######################################################################################################################################
SUBMIT_CONSUMABLE_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="submit_consumable",
        description="提交本次合成的消耗品规格（名称、描述与内置伤害卡规格）。校验不通过会返回错误，可按提示修正后重提；全部通过后再调用 finish_consumable 结束。",
        parameters={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "消耗品全名，采用「消耗品.XXXX」命名格式，体现材料特性与用途",
                },
                "description": {
                    "type": "string",
                    "description": "物品描述，30-60字，说明外观、气味或使用感受",
                },
                "card": {
                    "type": "object",
                    "description": "该消耗品在战斗中被转化为手牌时的卡牌规格；card 内不包含 name/description（由系统沿用消耗品的）。消耗品卡固定 0 费、一次性，只做伤害。",
                    "properties": {
                        "on_play_affixes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "maxItems": 2,
                            "description": "即时词缀（多值列表）；本卡被打出时结算，仅本次出牌生效；每个元素是一条完整独立词缀，格式 `[词缀名]:机械结算描述`，禁止拆分或合并；无则 []",
                        },
                        "damage": {
                            "type": "integer",
                            "description": f"单次伤害（必填），范围 {CONSUMABLE_DAMAGE_MIN}..{CONSUMABLE_DAMAGE_MAX}",
                        },
                        "hit_count": {
                            "type": "integer",
                            "description": f"攻击次数（多段各自独立结算），1..{CONSUMABLE_HIT_COUNT_MAX}，默认 1",
                        },
                        "target_type": {
                            "type": "string",
                            "enum": ["single", "all", "spread"],
                            "description": "目标类型：single 单体、all 阵营全体、spread 散射",
                        },
                    },
                    "required": [
                        "on_play_affixes",
                        "damage",
                        "hit_count",
                        "target_type",
                    ],
                },
            },
            "required": ["name", "description", "card"],
        },
    )
)


#######################################################################################################################################
FINISH_CONSUMABLE_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="finish_consumable",
        description="消耗品规格已通过 submit_consumable 成功提交后调用，结束本次合成。",
        parameters={"type": "object", "properties": {}},
    )
)


#######################################################################################################################################
def _handle_list_consumable_examples() -> str:
    """处理 list_consumable_examples 工具调用：返回消耗品卡牌原型的 index 纵览。"""
    index = [
        {
            "id": item["prototype_id"],
            "name": item["name"],
            "summary": item["summary"],
            "keywords": item["keywords"],
        }
        for item in list_card_prototype_index(card_type="消耗品")
    ]
    logger.info(
        f"[CraftConsumableItemActionSystem] list_consumable_examples 执行: 共 {len(index)} 个示例"
    )
    return json.dumps(index, ensure_ascii=False)


#######################################################################################################################################
def _handle_get_consumable_example(example_id: str) -> str:
    """处理 get_consumable_example 工具调用：按 id 返回完整卡牌原型（含 card 规格）。"""
    try:
        proto = get_card_prototype(example_id)
    except ValueError as e:
        return f"错误：{e}。可用 id 请通过 list_consumable_examples 查询。"
    if proto.card_type != "消耗品":
        return f"错误：{example_id!r} 不是消耗品卡牌原型，可用 id 请通过 list_consumable_examples 查询。"
    logger.info(
        f"[CraftConsumableItemActionSystem] get_consumable_example 执行: {example_id}"
    )
    return json.dumps(
        {
            "id": proto.prototype_id,
            "name": proto.name,
            "summary": proto.summary,
            "keywords": json.loads(proto.keywords_json),
            "design": proto.design,
            "card": json.loads(proto.card_json),
        },
        ensure_ascii=False,
    )


#######################################################################################################################################
def _handle_submit_consumable(
    results: List[_CraftConsumableSpec],
    name: str,
    description: str,
    card: Dict[str, Any],
) -> str:
    """处理 submit_consumable 工具调用：校验并暂存消耗品规格。"""
    assert name, "name 不能为空"
    spec = _CraftConsumableSpec(name=name, description=description, **card)

    # 纯伤害约束（本阶段）：伤害必填且在护栏内、目标类型合法。
    if not (CONSUMABLE_DAMAGE_MIN <= spec.damage <= CONSUMABLE_DAMAGE_MAX):
        return (
            f"错误：damage 必须在 {CONSUMABLE_DAMAGE_MIN}..{CONSUMABLE_DAMAGE_MAX} 之间"
            f"（当前 {spec.damage}）。请修正后重新调用 submit_consumable。"
        )
    if not (1 <= spec.hit_count <= CONSUMABLE_HIT_COUNT_MAX):
        return (
            f"错误：hit_count 必须在 1..{CONSUMABLE_HIT_COUNT_MAX} 之间"
            f"（当前 {spec.hit_count}）。请修正后重新调用 submit_consumable。"
        )
    if spec.target_type not in CONSUMABLE_TARGET_TYPES:
        return f"错误：target_type 无效（{spec.target_type!r}）。请修正后重新提交。"

    # 构造探针卡：固定 0 费、一次性、纯伤害。
    probe = Card(
        name=spec.name,
        description=spec.description,
        on_play_affixes=spec.on_play_affixes,
        on_hit_affixes=[],
        on_turn_end_affixes=[],
        playable=True,
        exhaust=True,
        retain=False,
        ethereal=False,
        transferable=False,
        cost=0,
        damage=spec.damage,
        hit_count=spec.hit_count,
        block=0,
        target_type=TargetType(spec.target_type),
    )
    for affix in probe.on_play_affixes:
        result = validate_affix_slot("on_play_affixes", affix, probe)
        if not result.ok:
            return (
                f"错误：on_play_affixes 词缀不合法：{result.reason}。"
                "请修正后重新调用 submit_consumable。"
            )

    results.append(spec)
    logger.info(
        f"[CraftConsumableItemActionSystem] submit_consumable 执行:\n"
        f"  name: {spec.name}\n"
        f"  damage: {spec.damage} / hit_count: {spec.hit_count} / target_type: {spec.target_type}"
    )
    return f"已记录：{spec.name}。确认无误后调用 finish_consumable 结束。"


#######################################################################################################################################
def _handle_finish_consumable() -> str:
    """处理 finish_consumable 工具调用（无参，仅作为终止信号）。"""
    return "已结束本次消耗品合成。"


#######################################################################################################################################
@prompt_builder
def _build_craft_consumable_prompt(materials: List[MaterialItem]) -> str:
    """构建合成消耗品的 LLM 提示词。"""
    material_lines = "\n".join(
        f"- **{m.name}**（数量 {m.count}）：{m.description}" for m in materials
    )

    return f"""# 任务：根据材料创意合成一件消耗品

## 投入材料

{material_lines}

## 消耗品叙事

- **name**：消耗品全名，采用「消耗品.XXXX」命名格式，体现材料特性与用途，简洁有辨识度
- **description**：物品描述，30-60字，说明外观、气味或使用感受，体现材料的来源

## 卡牌规格（card）

`card` 是这件消耗品在战斗中被转化为手牌时的卡牌规格；`card` 内不输出 `name`/`description`（由系统沿用消耗品的）。
消耗品卡**固定 0 费（cost=0）且一次性（exhaust=True）**，本阶段**只做伤害**：只会用到 `card` 中的 `on_play_affixes` / `damage` / `hit_count` / `target_type` 四个字段，其余骨架字段（cost / exhaust / block 等）由系统固定，无需你输出。

{BUILD_CARD_FIELD_DESCRIPTION}

{AFFIX_DESIGN_SPEC}

## 本阶段附加约束

- `damage` 必填且在 {CONSUMABLE_DAMAGE_MIN}..{CONSUMABLE_DAMAGE_MAX} 之间；`hit_count` 在 1..{CONSUMABLE_HIT_COUNT_MAX} 之间。
- `target_type` 只允许 `single` / `all` / `spread`；不做自我治疗、不做格挡、不做状态。
- `on_play_affixes` 可为空；若填写，只能追加伤害类效果（如 `[灼烧]:打出时对目标追加本卡 damage×1 的伤害`）。

## 工作流程

1. 准备阶段：调用 `list_consumable_examples` 纵览可用消耗品示例的索引，结合本次投入材料筛选最相关的示例；
2. 精读阶段：如需，调用 `get_consumable_example` 获取 1~2 个最相关示例的完整卡牌规格；
3. 提交阶段：综合材料特性与示例参照，调用 `submit_consumable` 提交本次合成的消耗品规格；若返回错误，按提示修正后重新提交；
4. 结束后：`submit_consumable` 成功后再调用 `finish_consumable` 结束对话。提交时无需在 content 中展开长篇推导，把分析过程浓缩在内心即可。"""


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
        """执行完整合成流程。

        Args:
            entity: 携带 CraftConsumableItemAction 的工坊世界实体
        """
        action = entity.get(CraftConsumableItemAction)

        storage_entity = self._game.get_storage_entity()
        if storage_entity is None or not storage_entity.has(StorageComponent):
            logger.error(
                "[CraftConsumableItemActionSystem] 全局储物箱实体不存在或缺少 StorageComponent"
            )
            return

        # 材料列表由 activate_craft_consumable 预填充（count = 本次使用量）
        materials = action.material_items

        # 调用消耗品工坊 agent（agent_loop 工具调用模式）推理生成卡牌规格
        prompt = _build_craft_consumable_prompt(materials)

        # 上下文隔离：仅取世界实体的首条 SystemMessage 作为「设定」，
        # 传入全新列表（agent_loop 原地追加），结束后不写回宿主实体持久记忆。
        agent_memory = self._game.get_agent_memory(entity)
        assert agent_memory.messages, "消耗品工坊世界实体缺少首条 SystemMessage"
        assert isinstance(
            agent_memory.messages[0], SystemMessage
        ), "消耗品工坊世界实体 AI 记忆的第一条消息必须是 SystemMessage"
        messages: List[ChatMessage] = [agent_memory.messages[0]]

        specs: List[_CraftConsumableSpec] = []

        try:
            success = await agent_loop(
                name=entity.name,
                input_message=prompt,
                messages=messages,
                tools=[
                    LIST_CONSUMABLE_EXAMPLES_TOOL,
                    GET_CONSUMABLE_EXAMPLE_TOOL,
                    SUBMIT_CONSUMABLE_TOOL,
                    FINISH_CONSUMABLE_TOOL,
                ],
                handlers={
                    LIST_CONSUMABLE_EXAMPLES_TOOL.function.name: _handle_list_consumable_examples,
                    GET_CONSUMABLE_EXAMPLE_TOOL.function.name: _handle_get_consumable_example,
                    SUBMIT_CONSUMABLE_TOOL.function.name: partial(
                        _handle_submit_consumable, specs
                    ),
                    FINISH_CONSUMABLE_TOOL.function.name: _handle_finish_consumable,
                },
                max_rounds=8,
                terminal_tools=[FINISH_CONSUMABLE_TOOL],
            )
        except Exception as e:
            logger.error(f"[CraftConsumableItemActionSystem] agent_loop 异常: {e}")
            return

        if not success:
            logger.error("[CraftConsumableItemActionSystem] agent_loop 失败，中止")
            return

        if not specs:
            logger.error(
                "[CraftConsumableItemActionSystem] LLM 结束但未成功提交消耗品规格，中止"
            )
            return

        result = specs[0]

        # 由 LLM 产出的卡牌规格构造完整 Card；固定 0 费、一次性、纯伤害。
        card = Card(
            name=result.name,
            description=result.description,
            on_play_affixes=result.on_play_affixes,
            on_hit_affixes=[],
            on_turn_end_affixes=[],
            playable=True,
            exhaust=True,
            retain=False,
            ethereal=False,
            transferable=False,
            cost=0,
            damage=result.damage,
            hit_count=result.hit_count,
            block=0,
            target_type=TargetType(result.target_type),
        )

        # 更新 StorageComponent：扣减材料 + 追加成品
        new_item = ConsumableItem(
            name=result.name,
            description=result.description,
            cards=[card],
            resources=action.material_items,
        )
        self._update_storage(storage_entity, action.material_names, new_item)

        logger.info(
            f"[CraftConsumableItemActionSystem] 合成完成: {new_item.name} "
            f"cards={new_item.cards}"
        )

    ####################################################################################################################################
    def _update_storage(
        self,
        storage_entity: Entity,
        material_names: List[str],
        new_item: ConsumableItem,
    ) -> None:
        """扣减已用材料（跨同名条目结转、归零移除），并入合成品到 StorageComponent。"""
        storage = storage_entity.get(StorageComponent)

        updated_items = deduct_materials(storage.items, material_names)
        updated_items = append_item_with_stacking(updated_items, new_item)

        storage_entity.replace(StorageComponent, storage.name, updated_items)
