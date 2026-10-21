"""卡牌公共层：卡牌设计引擎与卡牌记忆标记的单点实现。

设计侧被战利品 / 装备工坊 / 消耗品工坊 / 怪物牌库共用（选型、设计契约、落地），
记忆侧被出牌与传递共用（卡牌 → 审计用精简 JSON）。差异留在各自 system 文件中，
本模块只放必须同构的部分，避免契约与字段口径漂移。

其中「为某个 actor 造牌」的两条路径（战利品 / 怪物牌库）统一走本模块的
actor 上下文入口：宿主是世界实体「世界.卡牌设计」，system prompt 取它自己的，
目标 actor 的 system prompt 作为任务提示词里的数据块注入，会话结束不留痕。

``uuid`` 由计算端持有：LLM 只用编号定位，回填由本模块完成。
"""

import json
from dataclasses import dataclass
from functools import partial
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Final,
    List,
    Optional,
    Set,
    Tuple,
    Union,
)
from uuid import uuid4

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from ..deepseek import agent_loop
from ..entitas import Entity, Matcher
from ..game.dbg_game import DBGGame
from ..llm import ToolDefinition, ToolFunction
from ..models import (
    DESIGNABLE_AFFIX_FIELDS,
    Card,
    CardDesignComponent,
    ChatMessage,
    NormalizedStrList,
    SystemMessage,
    apply_affix_design,
    apply_numeric_design,
    normalize_str_list,
    validate_affix_slot,
)
from ..pgsql import CardPrototypeIndexEntry, get_card_prototype
from ..utils import prompt_builder


#######################################################################################################################################
@dataclass
class Candidate:
    """一张待设计的候选卡 = 骨架卡 + 原型检索元数据 + 专属设计说明。"""

    card: Card
    archetype: str
    archetype_subtype: str
    summary: str
    design: str


#######################################################################################################################################
@dataclass
class DesignOutcome:
    """一次卡牌设计会话的结果；``bool(outcome)`` 等于 agent_loop 是否成功。

    ``designed`` 为实际落地张数（可能少于 ``total``，例如 agent 未提交全部卡就结束），
    调用方可据此判断是否需要回退。
    """

    ok: bool
    designed: int
    total: int
    affixes: int

    def __bool__(self) -> bool:
        return self.ok


#######################################################################################################################################
class CardDesign(BaseModel):
    """submit_card 提交的单张卡设计（name / description + 可选数值微调 + 词缀）。

    `extra="allow"` 用于承载调用方通过 `run_card_design_session(extra_properties=...)`
    追加的领域字段（如装备的 speed）；这些字段在 `model_extra` 中读取。
    """

    model_config = ConfigDict(extra="allow")

    uuid: str
    name: str
    description: str
    cost: Optional[int] = None
    damage: Optional[int] = None
    hit_count: Optional[int] = None
    block: Optional[int] = None
    # 词缀（多值）：agent 在原型已存在的槽位内重新设计；缺省 / 不合格则置空。
    on_play_affixes: Optional[NormalizedStrList] = None
    on_hit_affixes: Optional[NormalizedStrList] = None
    on_turn_end_affixes: Optional[NormalizedStrList] = None
    on_autonomous_affixes: Optional[NormalizedStrList] = None


#######################################################################################################################################
_SUBMIT_CARD_DESCRIPTION: Final[str] = (
    "提交一张卡的设计（name / description + 可选数值微调 + 词缀）。每张卡各调用一次，用编号（#N）定位。词缀只能作用于 HP（伤害 / 反伤 / 吸血 / 治疗）或经 transferable 牌施加持续状态；不得写格挡、抽弃牌、能量、改布尔标志。`block` 只能作为数值来源（base），不能作为效果结果——不要写「获得 / 增加 / 回复格挡」。只能引用内建数值（本卡 damage/block/hit_count、目标与自身 HP/最大HP/总格挡）；机械结算描述直接写效果，不要以「打出时 / 被命中时 / 回合结束时 / 自主运行」开头（界面已显示时机）。提交到未开放槽或格式不合法会被丢弃。"
)

# submit_card 的基础字段；调用方可经 build_submit_card_tool 追加领域字段（如装备 speed）。
_SUBMIT_CARD_PROPERTIES: Final[Dict[str, Any]] = {
    "card_index": {
        "type": "integer",
        "description": "候选卡编号（任务清单里的 #N，从 1 开始）",
    },
    "name": {
        "type": "string",
        "description": "设计后的卡牌名",
    },
    "description": {
        "type": "string",
        "description": "设计后的叙事描述（叙事锚点：不含数值，不重述字段已确定的效果）",
    },
    "cost": {
        "type": "integer",
        "description": "可选：在原型基础上微调本卡 cost；不给则沿用原型。",
    },
    "damage": {
        "type": "integer",
        "description": "可选：在原型基础上微调本卡 damage；不给则沿用原型。",
    },
    "hit_count": {
        "type": "integer",
        "description": "可选：在原型基础上微调本卡 hit_count（攻击次数）；不给则沿用原型。",
    },
    "block": {
        "type": "integer",
        "description": "可选：在原型基础上微调本卡 block（持有期格挡）；不给则沿用原型。",
    },
    "on_play_affixes": {
        "type": "array",
        "items": {"type": "string"},
        "maxItems": 1,
        "description": "本卡打出时结算的即时词缀（可选，至多一条）：数组长度≤1，元素形如 `[词缀名]:机械结算描述`；无则 []。仅当原型该槽非空（有引导）时可提交；须满足词缀格式，否则整槽置空。`block` 只能作为数值来源，不能写成获得格挡；描述直接写效果，不要重复时机词。",
    },
    "on_hit_affixes": {
        "type": "array",
        "items": {"type": "string"},
        "maxItems": 1,
        "description": "本卡持有者被命中时触发的受击词缀（可选，至多一条）：数组长度≤1，元素形如 `[词缀名]:机械结算描述`；无则 []。仅当原型该槽非空时可提交；须满足词缀格式。`block` 只能作为数值来源，不能写成获得格挡；描述直接写效果，不要重复时机词。",
    },
    "on_turn_end_affixes": {
        "type": "array",
        "items": {"type": "string"},
        "maxItems": 1,
        "description": "持有者每次 pass turn 结算的回合结束词缀（可选，至多一条）：数组长度≤1，元素形如 `[词缀名]:机械结算描述`；无则 []。仅当原型该槽非空时可提交；须满足词缀格式。`block` 只能作为数值来源，不能写成获得格挡；描述直接写效果，不要重复时机词。",
    },
    "on_autonomous_affixes": {
        "type": "array",
        "items": {"type": "string"},
        "maxItems": 1,
        "description": "卡牌自主运行词缀（可选，至多一条）：数组长度≤1，元素形如 `[词缀名]:机械结算描述`；持有者每次 pass turn（回合结束词缀之后）结算，效果目标可为场上任意存活角色（敌人/友方/持有者，由词缀文本决定），不锁定持有者；无则 []。仅当原型该槽非空时可提交；须满足词缀格式。`block` 只能作为数值来源，不能写成获得格挡；描述直接写效果，不要重复时机词。",
    },
}


#######################################################################################################################################
def build_submit_card_tool(
    extra_properties: Optional[Dict[str, Any]] = None,
    extra_required: Optional[List[str]] = None,
) -> ToolDefinition:
    """构建 submit_card 工具。

    `extra_properties` 为可选的领域扩展字段（name → JSON schema）；`extra_required`
    为必须一并提交的扩展字段名。领域字段直接进 schema，调用方的提示词不必再复述其范围。
    """
    properties: Dict[str, Any] = dict(_SUBMIT_CARD_PROPERTIES)
    if extra_properties:
        properties.update(extra_properties)
    required = ["card_index", "name", "description"]
    if extra_required:
        required.extend(extra_required)
    return ToolDefinition(
        function=ToolFunction(
            name="submit_card",
            description=_SUBMIT_CARD_DESCRIPTION,
            parameters={
                "type": "object",
                "properties": properties,
                "required": required,
            },
        )
    )


SUBMIT_CARD_TOOL = build_submit_card_tool()


#######################################################################################################################################
FINISH_CARDS_TOOL = ToolDefinition(
    function=ToolFunction(
        name="finish_cards",
        description=(
            "全部卡均已通过 submit_card 成功提交后调用，结束本次设计；若仍有未提交或被拒的卡，调用会返回错误并提示缺哪几张。"
        ),
        parameters={"type": "object", "properties": {}},
    )
)


#######################################################################################################################################
LIST_CARD_PROTOTYPES_TOOL = ToolDefinition(
    function=ToolFunction(
        name="list_card_prototypes",
        description="纵览当前可选卡牌原型的索引（id / archetype / archetype_subtype / name / summary / keywords），用于选型前建立全局观。",
        parameters={"type": "object", "properties": {}},
    )
)


#######################################################################################################################################
GET_CARD_PROTOTYPE_TOOL = ToolDefinition(
    function=ToolFunction(
        name="get_card_prototype",
        description="按 id 获取某个卡牌原型的完整规格（name / summary / design / card 全字段），用于精读候选。",
        parameters={
            "type": "object",
            "properties": {
                "prototype_id": {
                    "type": "string",
                    "description": "原型 id，必须来自 list_card_prototypes 返回的索引",
                },
            },
            "required": ["prototype_id"],
        },
    )
)


#######################################################################################################################################
def build_select_cards_tool(size: int) -> ToolDefinition:
    """构建选型工具：一次性提交恰好 `size` 个原型 id（同一原型可重复）。"""
    return ToolDefinition(
        function=ToolFunction(
            name="select_cards",
            description=(
                f"一次性提交恰好 {size} 个原型 id（同一原型可重复），确定选型；随后进入逐张设计。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "prototype_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": size,
                        "maxItems": size,
                        "description": f"恰好 {size} 个原型 id，必须来自 list_card_prototypes 返回的索引，可重复",
                    },
                },
                "required": ["prototype_ids"],
            },
        )
    )


#######################################################################################################################################
def materialize_candidate(prototype_id: str, source: str) -> Optional[Candidate]:
    """按 prototype_id 物化一张独立候选卡（换新 uuid、回填 source、附设计说明）。

    原型 uuid 是共享常量，必须换新；`source` 回填持有者名（牌库 / 奖励入口不变量）。
    """
    try:
        # 获取原型并解析为 Card 对象
        proto = get_card_prototype(prototype_id)

        # 解析原型的 JSON 数据为 Card 对象
        card = Card.model_validate(json.loads(proto.card_json))

    except Exception as e:
        logger.error(f"[card_design] 获取/解析原型 {prototype_id!r} 失败: {e}")
        return None

    # 为候选卡生成新的 uuid 并回填 source
    card.uuid = str(uuid4())
    card.source = source
    return Candidate(
        card=card,
        archetype=proto.archetype,
        archetype_subtype=proto.archetype_subtype,
        summary=proto.summary,
        design=proto.design,
    )


#######################################################################################################################################
def format_candidate(candidate: Candidate, index: int) -> str:
    """单张候选卡的 prompt 片段：编号 + 可设计槽位 + 原型专属设计说明。

    uuid 由计算端持有并用于最终绑定，不暴露给 LLM；LLM 只需引用编号 #N。
    骨架数值与只读标志已写在 design 的【骨架】里，此处不重复；
    原型的占位词缀也不再单列——变量池与方向已含在 design 的【设计】里。
    """
    card = candidate.card
    designable = [field for field in DESIGNABLE_AFFIX_FIELDS if getattr(card, field)]
    slots = "、".join(designable) if designable else "无（仅设计 name/description）"
    return f"- #{index}\n  原型: {candidate.archetype} / {candidate.archetype_subtype} — {candidate.summary}\n  可设计槽: {slots}\n  设计: {candidate.design}"


#######################################################################################################################################
@prompt_builder
def build_card_design_prompt(candidates: List[Candidate], context: str = "") -> str:
    """卡牌设计提示词：逐卡给出原型骨架 + 专属 design。

    不强调「奖励」——本质上就是「给原型 + 依上下文生成卡牌」。
    `context` 为可选的任务前言（如工坊的投入材料）；为空时不出现。
    骨架 / design / 可设计槽逐卡给出；数值、只读与槽位等提交约束在 submit_card 的
    schema 里，词缀的通用硬边界（只写 HP / 内建数值 / 作用对象）也随该 schema 下发，
    因此本提示词只保留「生成任务 + 叙事约束」。
    """
    card_lines = "\n\n".join(
        format_candidate(c, i) for i, c in enumerate(candidates, 1)
    )
    context_block = f"{context.strip()}\n\n" if context.strip() else ""
    return f"""# 任务：为下列原型生成卡牌

{context_block}依据你的设定与上面给出的上下文，为每个原型设计 `name`、`description`，并在开放槽位内补充词缀。卡牌是任意一种能被解释成战斗资源的存在，不必是动作。

## 原型

{card_lines}

## 叙事

- `description` 不含数值、不重述效果；`name` 简洁有辨识度。
- **场景中立（生命周期）**：卡牌会长期留在牌库与角色身上，而当前场景终将销毁；因此 `name` / `description` / 词缀文本都不得依赖当前场景、地点、在场者、场景中的具体物件或刚发生的事，否则卡牌日后会指向一个已不存在的东西。只取材于角色的系统设定（历史/性格/禁忌/最爱/体型/技艺/典故），换到任何场景都成立。
- **自主槽的取材**：若某张候选卡开放 `on_autonomous_affixes`，把自主主体写成角色身边的伙伴或旧物（见「艺术锚点」与角色设定里的伙伴），效果写成它自己的行为；其它槽位可以提到它，但不得让它代替角色成为效果主体。角色没有这类伙伴时，按原型 design 给出的自主意象来写。

对每张卡调用一次 `submit_card` 提交其设计；全部提交后调用 `finish_cards` 结束。"""


#######################################################################################################################################
def _handle_submit_card(
    edits: List[CardDesign],
    cards: List[Card],
    card_index: int = 0,
    name: str = "",
    description: str = "",
    cost: Optional[int] = None,
    damage: Optional[int] = None,
    hit_count: Optional[int] = None,
    block: Optional[int] = None,
    on_play_affixes: Optional[NormalizedStrList] = None,
    on_hit_affixes: Optional[NormalizedStrList] = None,
    on_turn_end_affixes: Optional[NormalizedStrList] = None,
    on_autonomous_affixes: Optional[NormalizedStrList] = None,
    **extra: Any,
) -> str:
    """处理 submit_card：按 #N 定位候选卡（uuid 由计算端持有），校验词缀后暂存。

    `card_index` / `name` / `description` 在 schema 里是必填，但模型偶尔会漏传；
    这里给出可读的错误，而不是让 TypeError 冒到 agent_loop。
    """
    if not name.strip():
        return "错误：缺少 name。"
    if not description.strip():
        return "错误：缺少 description。"
    if not (1 <= card_index <= len(cards)):
        return f"错误：card_index 超出范围（应为 1..{len(cards)}）。"
    card = cards[card_index - 1]

    submitted_map: Dict[str, Optional[NormalizedStrList]] = {
        "on_play_affixes": on_play_affixes,
        "on_hit_affixes": on_hit_affixes,
        "on_turn_end_affixes": on_turn_end_affixes,
        "on_autonomous_affixes": on_autonomous_affixes,
    }

    problems: List[str] = []
    for field in DESIGNABLE_AFFIX_FIELDS:
        #   获取提交的词缀列表并进行标准化
        items = normalize_str_list(submitted_map.get(field) or [])

        #   如果该槽位在原型中不可设计，则跳过校验
        if not getattr(card, field):
            if items:
                #   如果提交了不可设计的词缀，则记录问题
                problems.append(f"{field} 不可设计（原型该槽无引导），请勿提交")
            continue

        #   每个槽至多一条词缀（schema maxItems=1 外的兜底）
        if len(items) > 1:
            problems.append(
                f"{field} 每个槽至多一条词缀，收到 {len(items)} 条，请只保留一条"
            )
            continue

        #   遍历每个提交的词缀，进行合法性校验
        for affix in items:
            result = validate_affix_slot(field, affix, card)
            if not result.ok:
                problems.append(f"{field}: {affix!r} → {result.reason}")

    # 如果存在问题，返回错误信息并终止本次提交
    if problems:
        detail = "\n".join(f"- {p}" for p in problems)
        return "错误：词缀不合法，本卡未记录。请修正后重新调用 submit_card：\n" + detail

    edits.append(
        CardDesign(
            uuid=card.uuid,
            name=name,
            description=description,
            cost=cost,
            damage=damage,
            hit_count=hit_count,
            block=block,
            on_play_affixes=on_play_affixes,
            on_hit_affixes=on_hit_affixes,
            on_turn_end_affixes=on_turn_end_affixes,
            on_autonomous_affixes=on_autonomous_affixes,
            **extra,
        )
    )
    logger.info(f"[card_design] submit_card: #{card_index} {card.uuid} → {name}")
    return "已记录该卡的设计。"


#######################################################################################################################################
def _handle_finish_cards(edits: List[CardDesign], cards: List[Card]) -> str:
    """处理 finish_cards：仅当全部候选卡都已有成功提交的设计时，才允许结束。"""
    designed = {edit.uuid for edit in edits}
    missing = [
        f"#{index + 1}" for index, card in enumerate(cards) if card.uuid not in designed
    ]
    if missing:
        raise ValueError(
            f"还有 {len(missing)} 张卡未成功提交（{'、'.join(missing)}）；请修正后重新调用 submit_card，全部完成后再 finish_cards。"
        )
    return "已结束本次设计。"


#######################################################################################################################################
class _CardSelection(BaseModel):
    """select_cards 的结果容器：选定的原型 id 列表（可重复）。"""

    prototype_ids: List[str] = Field(default_factory=list)


#######################################################################################################################################
def _handle_list_card_prototypes(index: List[CardPrototypeIndexEntry]) -> str:
    """处理 list_card_prototypes：返回原型索引纵览。"""
    payload = [
        {
            "id": item["prototype_id"],
            "archetype": item["archetype"],
            "archetype_subtype": item["archetype_subtype"],
            "name": item["name"],
            "summary": item["summary"],
            "keywords": item["keywords"],
        }
        for item in index
    ]
    logger.info(f"[card_design] list_card_prototypes: 共 {len(payload)} 个原型")
    return json.dumps(payload, ensure_ascii=False)


#######################################################################################################################################
def _handle_get_card_prototype(valid_ids: Set[str], prototype_id: str) -> str:
    """处理 get_card_prototype：按 id 返回完整原型（含 card 全字段）。"""
    if prototype_id not in valid_ids:
        return f"错误：未知原型 id {prototype_id!r}。可用 id 请通过 list_card_prototypes 查询。"
    try:
        proto = get_card_prototype(prototype_id)
    except ValueError as e:
        return f"错误：{e}。可用 id 请通过 list_card_prototypes 查询。"
    logger.info(f"[card_design] get_card_prototype: {prototype_id}")
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
def _handle_select_cards(
    selection: _CardSelection,
    valid_ids: Set[str],
    size: int,
    prototype_ids: List[str],
) -> str:
    """处理 select_cards：校验数量与 id 合法性，不合法则返回错误让 agent 修正重提。"""
    if len(prototype_ids) != size:
        return f"错误：需恰好 {size} 个 prototype_id，实际 {len(prototype_ids)}。请修正后重新调用 select_cards。"
    unknown = [pid for pid in prototype_ids if pid not in valid_ids]
    if unknown:
        return (
            f"错误：未知原型 id {unknown}。可用 id 请通过 list_card_prototypes 查询。"
        )
    selection.prototype_ids = list(prototype_ids)
    logger.info(f"[card_design] select_cards: {selection.prototype_ids}")
    return f"已记录 {len(selection.prototype_ids)} 个原型的选型。"


#######################################################################################################################################
@dataclass
class SelectionOutcome:
    """一次选型会话的结果；``bool(outcome)`` 为「agent_loop 成功且数量正确」。"""

    ok: bool
    selected: List[str]
    total: int

    def __bool__(self) -> bool:
        return self.ok and len(self.selected) == self.total


#######################################################################################################################################
def apply_designs(
    candidates: List[Candidate],
    edits: List[CardDesign],
    owner: str,
) -> Tuple[int, int, List[str]]:
    """把提交的设计写回候选卡，返回 (应用张数, 词缀条数, 告警列表)。

    按 `CardDesign.uuid`（计算端回填）定位候选；未知 uuid 记入告警并跳过。
    """
    by_uuid = {c.card.uuid: c.card for c in candidates}
    applied = 0
    affixes = 0
    notes: List[str] = []

    for edit in edits:
        # 根据提交的设计定位候选卡，若找不到则记录告警并跳过
        card = by_uuid.get(edit.uuid)
        if card is None:
            notes.append(f"未知 uuid {edit.uuid!r}，忽略")
            continue

        # 应用提交的设计到候选卡，包括名称、描述、数值和词缀
        card.name = edit.name
        card.description = edit.description
        # 骨架数值微调（不加护栏；None 表示沿用原型）
        apply_numeric_design(
            card,
            cost=edit.cost,
            damage=edit.damage,
            hit_count=edit.hit_count,
            block=edit.block,
        )
        # 词缀：在原型引导下重设计；不合法则整槽置空
        count, affix_notes = apply_affix_design(
            owner,
            card,
            {field: getattr(edit, field) for field in DESIGNABLE_AFFIX_FIELDS},
        )

        # 累计应用的词缀数量和记录告警信息
        affixes += count
        notes.extend(affix_notes)
        applied += 1

    return applied, affixes, notes


#######################################################################################################################################
async def run_card_design_session(
    name: str,
    candidates: List[Candidate],
    messages: List[ChatMessage],
    *,
    max_rounds: int = 6,
    context: str = "",
    extra_properties: Optional[Dict[str, Any]] = None,
    extra_required: Optional[List[str]] = None,
    on_design: Optional[Callable[[CardDesign], None]] = None,
    mutate_messages: bool = True,
) -> DesignOutcome:
    """跑一次卡牌设计会话：agent 逐卡 `submit_card`，计算端把设计写回候选卡。

    `candidates` 原地被设计（name / description / 数值 / 词缀）。返回 `DesignOutcome`；
    即便会话中途报错，已提交的设计仍会落地。`context` 为可选任务前言（如投入材料）。
    `extra_properties` / `extra_required` 给 submit_card 追加领域字段并声明其必填
    （如装备 speed，存入 `model_extra`）；`on_design` 在落地后对每条设计回调，
    供调用方读取扩展字段。`mutate_messages=False` 时在 `messages` 的浅拷贝上跑，
    用于保证「会话不写入调用方的记忆」。
    """
    edits: List[CardDesign] = []
    cards = [c.card for c in candidates]
    submit_tool = build_submit_card_tool(extra_properties, extra_required)

    # 定义工具处理函数映射，用于 agent_loop 调用
    handlers: Dict[str, Callable[..., Union[str, Awaitable[str]]]] = {
        submit_tool.function.name: partial(_handle_submit_card, edits, cards),
        FINISH_CARDS_TOOL.function.name: partial(_handle_finish_cards, edits, cards),
    }

    try:
        # 运行 agent_loop 进行卡牌设计会话
        result = await agent_loop(
            name=name,
            input_message=build_card_design_prompt(candidates, context),
            messages=messages,
            tools=[submit_tool, FINISH_CARDS_TOOL],
            handlers=handlers,
            terminal_tools=[FINISH_CARDS_TOOL],
            max_rounds=max_rounds,
            mutate_messages=mutate_messages,
        )

        # 判断 agent_loop 是否成功返回结果
        ok = bool(result)

    except Exception as e:
        logger.error(f"[card_design] {name} agent_loop 异常: {e}")
        ok = False

    applied, affixes, notes = apply_designs(candidates, edits, name)

    # 领域扩展字段（如装备 speed）回调
    if on_design is not None:
        for edit in edits:
            on_design(edit)

    # 输出设计过程中产生的告警信息
    for note in notes:
        logger.warning(f"[card_design] {name}: {note}")

    # 输出设计总结信息
    logger.info(
        f"[card_design] {name}: 设计 {applied}/{len(candidates)} 张，词缀 {affixes} 条（agent_loop 成功={ok}）"
    )
    return DesignOutcome(
        ok=ok, designed=applied, total=len(candidates), affixes=affixes
    )


#######################################################################################################################################
async def run_card_selection_session(
    name: str,
    index: List[CardPrototypeIndexEntry],
    messages: List[ChatMessage],
    *,
    size: int,
    prompt: str,
    max_rounds: int = 12,
    mutate_messages: bool = True,
) -> SelectionOutcome:
    """跑一次选型会话：agent 浏览原型库并用 `select_cards` 提交恰好 `size` 个 id。

    与具体玩法解耦的共用能力：怪物牌库选 5、消耗品工坊选 1 都用它。`prompt` 由调用方
    给出（含本次任务与上下文）；`messages` 通常为该 agent 的临时上下文。
    """
    if not index or size <= 0:
        logger.error(f"[card_design] {name} 选型失败：原型索引为空或 size 非法")
        return SelectionOutcome(ok=False, selected=[], total=size)

    valid_ids: Set[str] = {item["prototype_id"] for item in index}
    selection = _CardSelection()
    select_tool = build_select_cards_tool(size)
    try:
        result = await agent_loop(
            name=name,
            input_message=prompt,
            messages=messages,
            tools=[
                LIST_CARD_PROTOTYPES_TOOL,
                GET_CARD_PROTOTYPE_TOOL,
                select_tool,
            ],
            handlers={
                LIST_CARD_PROTOTYPES_TOOL.function.name: partial(
                    _handle_list_card_prototypes, index
                ),
                GET_CARD_PROTOTYPE_TOOL.function.name: partial(
                    _handle_get_card_prototype, valid_ids
                ),
                select_tool.function.name: partial(
                    _handle_select_cards, selection, valid_ids, size
                ),
            },
            max_rounds=max_rounds,
            terminal_tools=[select_tool],
            mutate_messages=mutate_messages,
        )
        ok = bool(result)
    except Exception as e:
        logger.error(f"[card_design] {name} 选型 agent_loop 异常: {e}")
        ok = False

    selected = selection.prototype_ids
    logger.info(
        f"[card_design] {name}: 选型 {len(selected)}/{size}（agent_loop 成功={ok}）"
    )
    return SelectionOutcome(ok=ok, selected=selected, total=size)


#######################################################################################################################################
# Actor 上下文的会话入口：以世界实体「世界.卡牌设计」为唯一宿主
#
# 怪物牌库（选型 + 设计）与战利品（设计）都走这里，口径统一：
# - system prompt 取世界实体自己的（设计契约，故事层）；
# - 目标 actor 的 system prompt（`agent_memory.messages[0]`）作为任务提示词里的数据块注入；
# - 会话跑在临时列表上（mutate_messages=False），结束即弃——actor 记忆不留痕，
#   它只从牌堆变更记录里知道「有候选 / 领了一张」，不知道牌是怎么设计出来的。
#
# 工坊（装备 / 消耗品）不走这条路：它们的上下文是工坊世界实体自己，不需要 actor 人设。
#######################################################################################################################################
# 请求 label 的分隔符：`世界.卡牌设计|角色.名`（与「世界.外观合成|角色.名」同构）
_ACTOR_LABEL_SEPARATOR: Final[str] = "|"


#######################################################################################################################################
def resolve_card_design_entity(game: DBGGame) -> Entity:
    """定位唯一的「卡牌设计」世界实体（蓝图必须提供，缺失即数据错误）。"""
    entities = game.get_group(Matcher(all_of=[CardDesignComponent])).entities.copy()
    assert (
        len(entities) == 1
    ), f"卡牌设计世界实体数量异常: {len(entities)}（应为 1 个 CardDesignComponent 世界实体）。蓝图缺少该实体时请刷新：python -m scripts.setup_demo"
    return next(iter(entities))


#######################################################################################################################################
def read_actor_system_prompt(game: DBGGame, actor_entity: Entity) -> str:
    """读目标 actor 的 system prompt（`agent_memory.messages[0]`，由 add_system_message 写入）。"""
    messages = game.get_agent_memory(actor_entity).messages
    assert messages and isinstance(
        messages[0], SystemMessage
    ), f"{actor_entity.name} 缺少首条 SystemMessage（add_system_message 未执行）"
    return messages[0].content


#######################################################################################################################################
def _actor_session_context(game: DBGGame, actor_name: str) -> Tuple[str, SystemMessage]:
    """取 (会话 label, 世界实体的 system prompt)；世界实体与 label 只解析一次。"""
    world_entity = resolve_card_design_entity(game)
    messages = game.get_agent_memory(world_entity).messages
    assert messages and isinstance(
        messages[0], SystemMessage
    ), f"{world_entity.name} 缺少首条 SystemMessage"
    return f"{world_entity.name}{_ACTOR_LABEL_SEPARATOR}{actor_name}", SystemMessage(
        content=messages[0].content
    )


#######################################################################################################################################
def _actor_prompt_block(actor_system_prompt: str) -> str:
    """把目标 actor 的 system prompt 渲染成任务提示词里的数据块。"""
    return f"## 你要为之设计的角色\n\n{actor_system_prompt.strip()}\n"


#######################################################################################################################################
def _actor_motif_block(motif: str) -> str:
    """把角色挂载的艺术锚点（`MotifComponent.motif`）渲染成任务提示词里的数据块。

    锚点描述的是「这个人」（母题 / 意象域 / 禁忌 / 命名口吻），与产物类型无关；
    空串时调用方不注入，消费口径回退到「只用角色设定」。
    """
    body = motif.strip()
    return f"## 艺术锚点\n\n以下是这个角色的取材锚点：设计时优先从这里取意象，「禁忌」不可越过。\n\n{body}\n"


#######################################################################################################################################
async def select_prototypes_for_actor(
    game: DBGGame,
    *,
    actor_name: str,
    actor_system_prompt: str,
    index: List[CardPrototypeIndexEntry],
    size: int,
    prompt: str,
    max_rounds: int = 12,
) -> SelectionOutcome:
    """为目标 actor 选型：上下文 = 世界契约（system）+ 该 actor 的设定（任务数据块）。"""
    label, system_message = _actor_session_context(game, actor_name)
    return await run_card_selection_session(
        label,
        index,
        [system_message],
        size=size,
        prompt=_actor_prompt_block(actor_system_prompt) + "\n" + prompt,
        max_rounds=max_rounds,
        mutate_messages=False,
    )


#######################################################################################################################################
async def design_cards_for_actor(
    game: DBGGame,
    *,
    actor_name: str,
    actor_system_prompt: str,
    candidates: List[Candidate],
    context: str = "",
    actor_motif: str = "",
    extra_properties: Optional[Dict[str, object]] = None,
    extra_required: Optional[List[str]] = None,
    on_design: Optional[Callable[[CardDesign], None]] = None,
    max_rounds: int = 16,
) -> DesignOutcome:
    """为目标 actor 设计候选卡：上下文口径同选型，会话结束不留痕。

    `actor_motif` 为角色挂载的艺术锚点（`MotifComponent.motif`）；非空时作为
    「## 艺术锚点」数据块注入，空串时行为与旧口径完全一致。
    """
    label, system_message = _actor_session_context(game, actor_name)
    session_context = _actor_prompt_block(actor_system_prompt)
    if actor_motif.strip():
        session_context += "\n" + _actor_motif_block(actor_motif)
    if context.strip():
        session_context += "\n" + context.strip() + "\n"

    return await run_card_design_session(
        label,
        candidates,
        [system_message],
        max_rounds=max_rounds,
        context=session_context,
        extra_properties=extra_properties,
        extra_required=extra_required,
        on_design=on_design,
        mutate_messages=False,
    )


#######################################################################################################################################
# 卡牌记忆标记：Card → 审计用精简 JSON
#######################################################################################################################################
#######################################################################################################################################
# 审计字段：卡牌自身的事实（不含 description / 词缀）
#######################################################################################################################################
def _card_audit_fields(card: Card) -> Dict[str, Any]:
    """卡牌的审计字段：身份 + 数值 + 目标类型。"""
    return {
        "name": card.name,
        "uuid": card.uuid,
        "source": card.source,
        "cost": card.cost,
        "damage": card.damage,
        "hit_count": card.hit_count,
        "block": card.block,
        "target_type": card.target_type.value,
    }


#######################################################################################################################################
# 传递副本：只记卡牌事实（副本归属由记忆正文说明）
#######################################################################################################################################
def build_received_card_tag(card: Card) -> str:
    """生成 `received_card` 标记值。"""
    return json.dumps(_card_audit_fields(card), ensure_ascii=False)
