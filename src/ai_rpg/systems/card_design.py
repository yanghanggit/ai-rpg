"""卡牌设计引擎：把「原型候选」交给角色 agent 设计成具体卡牌。

与具体玩法解耦。调用方负责候选的来源与最终去向；本模块只提供设计契约与流程：

- 设计契约：`submit_card` / `finish_cards` 两个工具；
- 提示词：`format_candidate` / `build_card_design_prompt`；
- 提交校验与落地：`apply_designs`（名称 / 描述 / 数值 / 词缀写回候选卡）；
- 一次完整设计会话：`run_card_design_session`（内部 agent_loop + 上述装配）。

`uuid` 全程由计算端持有：LLM 只用编号 `#N` 定位，`CardDesign.uuid` 由 `apply_designs`
从解析到的候选卡回填。

当前由 `GenerateSpoilsActionSystem` 使用；后续可供地下城怪物牌库等复用。
"""

import json
from dataclasses import dataclass
from functools import partial
from typing import Awaitable, Callable, Dict, List, Optional, Tuple, Union
from uuid import uuid4

from loguru import logger
from pydantic import BaseModel

from ..deepseek import ToolDefinition, ToolFunction, agent_loop
from ..models import (
    AFFIX_FIELDS,
    Card,
    ChatMessage,
    NormalizedStrList,
    apply_affix_design,
    apply_numeric_design,
    normalize_str_list,
    validate_affix_slot,
)
from ..pgsql import get_card_prototype
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
    """submit_card 提交的单张卡设计（name / description + 可选数值微调 + 词缀）。"""

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
SUBMIT_CARD_TOOL = ToolDefinition(
    function=ToolFunction(
        name="submit_card",
        description=(
            "提交一张卡的设计（name / description + 可选数值微调 + 词缀）。每张卡各调用一次，用编号（#N）定位。"
            "词缀只能作用于 HP（伤害 / 反伤 / 吸血 / 治疗）或经 transferable 牌施加持续状态；"
            "不得写格挡、抽弃牌、能量、改布尔标志，只能引用内建数值（本卡 damage/block/hit_count、"
            "目标与自身 HP/最大HP/总格挡）；提交到未开放槽或格式不合法会被丢弃。"
        ),
        parameters={
            "type": "object",
            "properties": {
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
                    "description": "本卡打出时结算的即时词缀（可选，至多一条）：数组长度≤1，元素形如 `[词缀名]:机械结算描述`；无则 []。仅当原型该槽非空（有引导）时可提交；须满足词缀格式，否则整槽置空。",
                },
                "on_hit_affixes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 1,
                    "description": "本卡持有者被命中时触发的受击词缀（可选，至多一条）：数组长度≤1，元素形如 `[词缀名]:机械结算描述`；无则 []。仅当原型该槽非空时可提交；须满足词缀格式。",
                },
                "on_turn_end_affixes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 1,
                    "description": "持有者每次 pass turn 结算的回合结束词缀（可选，至多一条）：数组长度≤1，元素形如 `[词缀名]:机械结算描述`；无则 []。仅当原型该槽非空时可提交；须满足词缀格式。",
                },
                "on_autonomous_affixes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 1,
                    "description": "卡牌自主运行词缀（可选，至多一条）：数组长度≤1，元素形如 `[词缀名]:机械结算描述`；持有者每次 pass turn（回合结束词缀之后）结算，效果目标可为场上任意存活角色（敌人/友方/持有者，由词缀文本决定），不锁定持有者；无则 []。仅当原型该槽非空时可提交；须满足词缀格式。",
                },
            },
            "required": ["card_index", "name", "description"],
        },
    )
)


#######################################################################################################################################
FINISH_CARDS_TOOL = ToolDefinition(
    function=ToolFunction(
        name="finish_cards",
        description="全部卡均已通过 submit_card 提交后调用，结束本次设计。",
        parameters={"type": "object", "properties": {}},
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
    designable = [field for field in AFFIX_FIELDS if getattr(card, field)]
    slots = "、".join(designable) if designable else "无（仅设计 name/description）"
    return (
        f"- #{index}\n"
        f"  原型: {candidate.archetype} / {candidate.archetype_subtype} — {candidate.summary}\n"
        f"  可设计槽: {slots}\n"
        f"  设计: {candidate.design}"
    )


#######################################################################################################################################
@prompt_builder
def build_card_design_prompt(candidates: List[Candidate]) -> str:
    """卡牌设计提示词：逐卡给出原型骨架 + 专属 design。

    不强调「奖励」——本质上就是「给原型 + 依上下文生成卡牌」。
    骨架 / design / 可设计槽逐卡给出；数值、只读与槽位等提交约束在 submit_card 的
    schema 里，词缀的通用硬边界（只写 HP / 内建数值 / 作用对象）也随该 schema 下发，
    因此本提示词只保留「生成任务 + 叙事约束」。
    """
    card_lines = "\n\n".join(
        format_candidate(c, i) for i, c in enumerate(candidates, 1)
    )
    return f"""# 任务：为下列原型生成卡牌

依据你的角色设定，为每个原型设计 `name`、`description`，并在开放槽位内补充词缀。卡牌可以是任意战斗资源——招式、物件、同伴、环境、状态等，不必是动作。

## 原型

{card_lines}

## 叙事

- `description` 不含数值、不重述效果；`name` 简洁有辨识度。
- **场景中立**：只取材于角色的系统设定（历史/性格/禁忌/最爱/体型/技艺/典故）；禁止写入当前场景、地点、在场者与刚发生的事，换到任何场景都成立。

对每张卡调用一次 `submit_card` 提交其设计；全部提交后调用 `finish_cards` 结束。"""


#######################################################################################################################################
def _handle_submit_card(
    edits: List[CardDesign],
    cards: List[Card],
    card_index: int,
    name: str,
    description: str,
    cost: Optional[int] = None,
    damage: Optional[int] = None,
    hit_count: Optional[int] = None,
    block: Optional[int] = None,
    on_play_affixes: Optional[NormalizedStrList] = None,
    on_hit_affixes: Optional[NormalizedStrList] = None,
    on_turn_end_affixes: Optional[NormalizedStrList] = None,
    on_autonomous_affixes: Optional[NormalizedStrList] = None,
) -> str:
    """处理 submit_card：按 #N 定位候选卡（uuid 由计算端持有），校验词缀后暂存。"""
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
    for field in AFFIX_FIELDS:

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
        )
    )
    logger.info(f"[card_design] submit_card: #{card_index} {card.uuid} → {name}")
    return "已记录该卡的设计。"


#######################################################################################################################################
def _handle_finish_cards() -> str:
    """处理 finish_cards 工具调用（无参，仅作为终止信号）。"""
    return "已结束本次设计。"


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
            {field: getattr(edit, field) for field in AFFIX_FIELDS},
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
) -> DesignOutcome:
    """跑一次卡牌设计会话：agent 逐卡 `submit_card`，计算端把设计写回候选卡。

    `candidates` 原地被设计（name / description / 数值 / 词缀）。返回 `DesignOutcome`；
    即便会话中途报错，已提交的设计仍会落地。
    """
    edits: List[CardDesign] = []
    cards = [c.card for c in candidates]

    # 定义工具处理函数映射，用于 agent_loop 调用
    handlers: Dict[str, Callable[..., Union[str, Awaitable[str]]]] = {
        SUBMIT_CARD_TOOL.function.name: partial(_handle_submit_card, edits, cards),
        FINISH_CARDS_TOOL.function.name: _handle_finish_cards,
    }

    try:

        # 运行 agent_loop 进行卡牌设计会话
        result = await agent_loop(
            name=name,
            input_message=build_card_design_prompt(candidates),
            messages=messages,
            tools=[SUBMIT_CARD_TOOL, FINISH_CARDS_TOOL],
            handlers=handlers,
            terminal_tools=[FINISH_CARDS_TOOL],
            max_rounds=max_rounds,
        )

        # 判断 agent_loop 是否成功返回结果
        ok = bool(result)

    except Exception as e:
        logger.error(f"[card_design] {name} agent_loop 异常: {e}")
        ok = False

    applied, affixes, notes = apply_designs(candidates, edits, name)

    # 输出设计过程中产生的告警信息
    for note in notes:
        logger.warning(f"[card_design] {name}: {note}")

    # 输出设计总结信息
    logger.info(
        f"[card_design] {name}: 设计 {applied}/{len(candidates)} 张，"
        f"词缀 {affixes} 条（agent_loop 成功={ok}）"
    )
    return DesignOutcome(
        ok=ok, designed=applied, total=len(candidates), affixes=affixes
    )
