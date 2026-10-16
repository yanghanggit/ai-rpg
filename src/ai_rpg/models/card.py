"""卡牌与状态效果模型定义。"""

import re
from dataclasses import dataclass
from typing import Final, List, Mapping, Optional, Tuple, final
from uuid import uuid4

from loguru import logger
from pydantic import BaseModel, Field, model_validator

from .str_list import NormalizedStrList, normalize_str_list
from .target_type import TargetType


###############################################################################################################################################
@final
class Card(BaseModel):
    """战斗卡牌"""

    name: str
    description: str  # 叙事锚点：不含数值，不重述其它字段已确定的效果
    on_play_affixes: NormalizedStrList = (
        []
    )  # 即时词缀（多值）：每个元素是一条完整独立词缀，格式 `[词缀名]:机械结算描述`；本卡被打出时结算，仅本次出牌生效；无则 []
    on_hit_affixes: NormalizedStrList = (
        []
    )  # 受击词缀（多值）：持有者被本次出牌命中时触发；无则 []
    on_turn_end_affixes: NormalizedStrList = (
        []
    )  # 回合结束词缀（多值）：持有者每次 pass turn 结算一次，只结算持有者本人手牌中带该词缀的牌；无则 []
    on_autonomous_affixes: NormalizedStrList = (
        []
    )  # 自主运行词缀（多值）：持有者每次 pass turn（在 on_turn_end 结算之后）由所在场景结算一次；效果目标为场上任意存活角色，由词缀文本决定；无则 []
    playable: bool = True  # 是否可出牌；False 时系统阻止出牌操作
    exhaust: bool = False  # 出牌后永久归入 ExhaustPile，不进入 DiscardPile 循环
    retain: bool = (
        False  # 回合末保留在手牌（不进入 DiscardPile），跨回合留在 HandComponent
    )
    ethereal: bool = False  # pass turn 时若仍留在手牌，自动移入 ExhaustPileComponent
    transferable: bool = (
        False  # 出牌时额外为每个解析目标手牌 copy 一份（副本 uuid 重新生成、transferable 置 False，不可再次传递；本体照常结算并进入弃牌/消耗流程）
    )
    cost: int = 1  # 出牌费用；消耗当前 energy；不足时禁止出牌
    damage: int = 0  # 单次伤害
    hit_count: int = 1  # 攻击次数；>1 时为多段攻击，每段独立结算
    block: int = 0  # 手牌持有期间提供的格挡；出牌仲裁时累加进持有者总防御
    target_type: TargetType = (
        TargetType.SINGLE
    )  # 目标类型，决定目标约束策略；SELF 锁定出牌者本人且无需 targets
    source: str = ""  # 卡牌来源（生成/注入者）名称；空字符串表示来源未知
    uuid: str = Field(default_factory=lambda: str(uuid4()))  # 全局唯一标识符

    @model_validator(mode="after")
    def _warn_flag_conflicts(self) -> "Card":
        """报警（不拦截）：检测布尔标志的互斥/死组合，仅记录告警日志。"""
        if self.retain and self.ethereal:
            logger.warning(
                f"Card「{self.name}」同时开启 retain 与 ethereal：二者互斥，"
                f"pass turn 时 ethereal 会先于回合末 retain 生效，retain 永不触发。"
            )
        if self.ethereal and self.on_autonomous_affixes:
            logger.warning(
                f"Card「{self.name}」同时开启 ethereal 与 on_autonomous_affixes："
                f"ethereal 会在自主运行阶段之前把牌移入 ExhaustPile，自主词缀永不触发。"
            )
        if not self.playable and self.transferable:
            logger.warning(
                f"Card「{self.name}」playable=false 但 transferable=true："
                f"牌不可出，transferable 永不触发，属无效组合。"
            )
        if not self.playable and self.exhaust:
            logger.warning(
                f"Card「{self.name}」playable=false 但 exhaust=true："
                f"牌不可出，exhaust 永不触发，属无效组合。"
            )
        return self


###############################################################################################################################################


#######################################################################################################################################
AFFIX_FIELDS: Final[Tuple[str, ...]] = (
    "on_play_affixes",
    "on_hit_affixes",
    "on_turn_end_affixes",
    "on_autonomous_affixes",
)

# 词缀硬格式：`[词缀名]:机械结算描述`（方括号 + 半/全角冒号缺一不可）。
# 与客户端 `readAffixLabel` 的解析保持一致（客户端按 `[名称]:说明` 取名）。
_AFFIX_FORMAT_RE: Final[re.Pattern[str]] = re.compile(
    r"^\[([^\[\]]+)\]\s*[:：]\s*([\s\S]*)$"
)


#######################################################################################################################################
@final
@dataclass(frozen=True)
class AffixValidationResult:
    """单条词缀的校验结果。"""

    ok: bool
    reason: str = ""


#######################################################################################################################################
def _split_affix(affix: str) -> Optional[Tuple[str, str]]:
    """拆分 `[词缀名]:机械结算描述`，返回 (名, 描述)；格式不符时返回 None。"""
    match = _AFFIX_FORMAT_RE.match(affix.strip())
    if match is None:
        return None
    return match.group(1).strip(), match.group(2).strip()


#######################################################################################################################################
def validate_affix_slot(
    affix_field: str,
    affix: str,
    card: Card,
) -> AffixValidationResult:
    """校验一条 agent 设计的词缀是否满足**硬不变量**。"""
    if affix_field not in AFFIX_FIELDS:
        return AffixValidationResult(False, f"未知词缀时机 {affix_field!r}")

    if affix_field == "on_play_affixes" and not card.playable:
        return AffixValidationResult(
            False, "不可出牌（playable=false）的牌不应有即时词缀"
        )

    if affix_field == "on_autonomous_affixes" and card.ethereal:
        return AffixValidationResult(
            False,
            "虚无牌（ethereal=true）会在自主运行阶段之前被移入 ExhaustPile，"
            "自主词缀永不触发，属无效组合",
        )

    split = _split_affix(affix)
    if split is None:
        return AffixValidationResult(
            False, "词缀必须形如 `[词缀名]:机械结算描述`（方括号与分隔符缺一不可）"
        )
    name, desc = split
    if not name:
        return AffixValidationResult(False, "词缀名为空")
    if not desc:
        return AffixValidationResult(False, "机械结算描述为空")
    if "词缀名" in name or "何种" in desc or "待设计" in desc:
        return AffixValidationResult(False, "仍是占位符，请替换为具体设计")

    return AffixValidationResult(True)


#######################################################################################################################################
def apply_affix_design(
    entity_name: str,
    card: Card,
    submitted: Mapping[str, Optional[List[str]]],
) -> Tuple[int, List[str]]:
    """把 agent 设计的词缀应用到 `card` 上，返回 (成功应用的条数, 说明列表)。"""
    applied = 0
    notes: List[str] = []

    for affix_field in AFFIX_FIELDS:
        if not getattr(card, affix_field):
            if submitted.get(affix_field):
                notes.append(f"{affix_field}: 原型该槽无引导，忽略设计提交")
            continue

        cleaned = normalize_str_list(submitted.get(affix_field) or [])
        if not cleaned:
            setattr(card, affix_field, [])
            notes.append(f"{affix_field}: 未提交或设计为空，置空（原型仅为引导）")
            continue

        results = [
            (affix, validate_affix_slot(affix_field, affix, card)) for affix in cleaned
        ]
        invalid = [(affix, result.reason) for affix, result in results if not result.ok]
        if invalid:
            setattr(card, affix_field, [])
            detail = "；".join(f"{affix!r}（{reason}）" for affix, reason in invalid)
            notes.append(
                f"{affix_field}: 不合法，整槽置空"
                f"（{entity_name} 卡「{card.name}」）— {detail}"
            )
        else:
            setattr(card, affix_field, cleaned)
            applied += len(cleaned)

    return applied, notes


#######################################################################################################################################
def apply_numeric_design(
    card: Card,
    *,
    cost: Optional[int] = None,
    damage: Optional[int] = None,
    hit_count: Optional[int] = None,
    block: Optional[int] = None,
) -> None:
    """把 agent 提交的骨架数值微调覆盖到 `card` 上（`None` 表示沿用原型）。"""
    if cost is not None:
        card.cost = cost
    if damage is not None:
        card.damage = damage
    if hit_count is not None:
        card.hit_count = hit_count
    if block is not None:
        card.block = block
