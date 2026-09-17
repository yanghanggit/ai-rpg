"""卡牌与状态效果模型定义。

本模块同时定义卡牌字段语义（`BUILD_CARD_FIELD_DESCRIPTION`）、词缀设计规范
（`AFFIX_DESIGN_SPEC`）与词缀设计校验（`validate_affix_slot` / `apply_affix_design`）。
"""

import re
from dataclasses import dataclass
from typing import Dict, Final, List, Mapping, Optional, Tuple, final
from uuid import uuid4

from loguru import logger
from pydantic import BaseModel, Field, model_validator

from .target_type import TargetType


###############################################################################################################################################
@final
class Card(BaseModel):
    """战斗卡牌"""

    name: str
    description: str  # 叙事锚点：不含数值，不重述其它字段已确定的效果
    on_play_affixes: List[str] = (
        []
    )  # 即时词缀；格式"[名称]:触发倾向描述"；本卡被打出时结算，仅本次出牌生效；无则 []
    on_hit_affixes: List[str] = (
        []
    )  # 受击词缀；格式"[名称]:触发倾向描述"；持有者被本次出牌命中时触发；无则 []
    on_turn_end_affixes: List[str] = (
        []
    )  # 回合结束词缀；格式"[名称]:触发倾向描述"；持有者每次 pass turn 结算一次，只结算持有者本人手牌中带该词缀的牌；无则 []
    playable: bool = True  # 是否可出牌；False 时系统阻止出牌操作
    exhaust: bool = False  # 出牌后永久归入 ExhaustPile，不进入 DiscardPile 循环
    retain: bool = (
        False  # 回合末保留在手牌（不进入 DiscardPile），跨回合留在 HandComponent
    )
    ethereal: bool = False  # pass turn 时若仍留在手牌，自动移入 ExhaustPileComponent
    transferable: bool = (
        False  # 出牌时从源手牌移除本体，copy 一份到每个解析目标手牌（副本 uuid 重新生成）
    )
    cost: int = 1  # 出牌费用；消耗当前 energy；不足时禁止出牌
    damage: int = 0  # 单次伤害
    hit_count: int = 1  # 攻击次数；>1 时为多段攻击，每段独立结算
    block: int = 0  # 手牌持有期间提供的格挡；出牌仲裁时累加进持有者总防御
    target_type: TargetType = (
        TargetType.SINGLE
    )  # 目标类型，决定目标约束策略；self_target=True 时忽略
    self_target: bool = False  # 锁定自身；True 时目标即出牌者本人，无需 targets
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
AFFIX_DESIGN_SPEC: Final[
    str
] = """## 词缀设计规范

词缀是你在骨架字段之上为角色设计的**增益 / 减益规则**，格式 `[词缀名]:机械结算描述`。它会被仲裁 LLM 直接执行，因此必须机制明确、可核验。

三个时机：

- `on_play_affixes`：本卡打出时结算，仅本次出牌生效。
- `on_hit_affixes`：本卡持有者被本次出牌命中时触发。
- `on_turn_end_affixes`：持有者每次 pass turn 结算一次（只结算其本人手牌中带该词缀的牌）。

### 一、字段锚点（硬性）

- 涉及**伤害**：描述中必须出现 `damage`，如 `对目标造成本卡 damage×2 的伤害`。
- 涉及**格挡 / 无视防御**：描述中必须出现 `block`，如 `无视目标 block`。
- 涉及**当前持有者**（可转移牌尤其）：必须用 `非 source 者` 指代，如 `对非 source 者结算本卡 damage 的持续伤害`。
- 作用对象只用规范称谓：`自身` / `出牌者` / `目标` / `本卡持有者` / `非 source 者`。

### 二、数值限制（只能引用字段 + 护栏内倍率）

- 伤害只能引用本卡 `damage`；格挡只能引用本卡 `block`；段数只能引用本卡 `hit_count`。
- 倍率范围：
  - `on_play_affixes`：`damage×1..3`、`block×1..3`、`hit_count×1..2`
  - `on_hit_affixes`：`damage×1..3`、`block×1..3`
  - `on_turn_end_affixes`：`damage×1..2`、`block×1..3`
- **禁止任何独立数值**（固定伤害、固定回合数、固定层数等）；状态标记只给名字，不给数字。
- 若本卡 `damage` 为 0，不得凭空造成伤害，只能用具名状态标记或引用 `block` 表达收益。

### 三、自身设计（角色视角）

- 从调色板选择对你的角色有利的方向：强健自身 `damage`、无视敌方格挡、反伤、持续伤害、挂状态标记、转嫁负面、分发增益/格挡、蓄势等。
- 可引用自由命名的状态标记（如「火焰」「破绽」），以与其它牌产生协同；命名与消费由你自行做出合理设计。
- 词缀名可自由创造；机械结算描述必须保持上述字段锚点与数值限制。
"""


#######################################################################################################################################
BUILD_CARD_FIELD_DESCRIPTION: Final[
    str
] = f"""## 卡牌字段语义

卡牌是战斗行动的最小单元：确定性骨架字段决定回合循环，语义词缀承载设计（见词缀设计规范）。

### 功能字段

| 字段 | 说明 |
| --- | --- |
| `playable` | 是否可出牌；false 时系统阻止出牌；默认 true |
| `exhaust` | 出牌后永久消耗，不进弃牌循环；默认 false |
| `retain` | 回合末保留在手牌，不进弃牌堆；默认 false |
| `ethereal` | pass turn 时若仍在手牌则自动消耗；默认 false |
| `transferable` | 出牌时从源手牌移除本体，并 copy 一份到每个目标手牌；默认 false |
| `cost` | 出牌费用（消耗 energy）；默认 1 |
| `damage` | 单次伤害；默认 0 |
| `hit_count` | 攻击次数，多段各自独立结算；默认 1 |
| `block` | 手牌持有期间提供的格挡；默认 0 |
| `self_target` | 锁定出牌者自身；true 时无需 targets |
| `target_type` | 目标类型（见下表）；`self_target=true` 时忽略 |

### 布尔标志的互斥与依赖

- `retain` 与 `ethereal` 互斥，禁止同时为 true：二者同属「回合边界手中牌去向」的两极，同时开启时 ethereal（pass turn 即消耗）先于 retain（回合末保留）生效，retain 失效。
- `transferable` 与 `exhaust` 均为「被打出时」结算，故为 true 时要求 `playable=true`；`playable=false` 时牌不可出，二者永不触发，属无效组合。

### 目标类型（target_type）

| 值 | 含义 |
| --- | --- |
| `{TargetType.SINGLE}` | 单个存活角色（默认） |
| `{TargetType.ALL}` | 阵营锚点：以指定目标为锚点，作用于其所在阵营（我方/敌方）的全部存活角色 |
| `{TargetType.SPREAD}` | 阵营锚点：散射锚点所在阵营的存活角色；hit_count 超过人数时每人至少一次，多余随机；否则纯随机 |

### source

`source` 记录牌来源（生成/注入者）名称，由系统填充，无需输出；`transferable` 的副本保留原 `source`。"""


#######################################################################################################################################
AFFIX_FIELDS: Final[Tuple[str, ...]] = (
    "on_play_affixes",
    "on_hit_affixes",
    "on_turn_end_affixes",
)

# 各时机下，字段倍率的上限（`damage×N` 的 N）。
_MAX_MULTIPLIERS: Final[Dict[str, Dict[str, int]]] = {
    "on_play_affixes": {"damage": 3, "block": 3, "hit_count": 2},
    "on_hit_affixes": {"damage": 3, "block": 3},
    "on_turn_end_affixes": {"damage": 2, "block": 3},
}

_MULTIPLIER_RE: Final[re.Pattern[str]] = re.compile(
    r"(damage|block|hit_count)\s*[×xX*]\s*(\d+)"
)
_DIGIT_RE: Final[re.Pattern[str]] = re.compile(r"\d+")

_DAMAGE_WORDS: Final[Tuple[str, ...]] = ("伤害", "受损")
_BLOCK_WORDS: Final[Tuple[str, ...]] = ("格挡", "防御")
_HOLDER_WORDS: Final[Tuple[str, ...]] = ("持有者", "持牌人", "牌主", "非 source")


#######################################################################################################################################
@final
@dataclass(frozen=True)
class AffixValidationResult:
    """单条词缀的校验结果。"""

    ok: bool
    reason: str = ""


#######################################################################################################################################
def _split_affix(affix: str) -> Optional[Tuple[str, str]]:
    """拆分 `[词缀名]:机械结算描述`，返回 (名, 描述)；无法拆分时返回 None。"""
    for sep in (":", "："):
        if sep in affix:
            name_part, desc = affix.split(sep, 1)
            name = name_part.strip().strip("[]【】").strip()
            return name, desc.strip()
    return None


#######################################################################################################################################
def validate_affix_slot(
    affix_field: str,
    affix: str,
    card: Card,
) -> AffixValidationResult:
    """校验一条 agent 设计的词缀是否满足字段锚点与数值护栏。"""
    if affix_field not in _MAX_MULTIPLIERS:
        return AffixValidationResult(False, f"未知词缀时机 {affix_field!r}")

    if affix_field == "on_play_affixes" and not card.playable:
        return AffixValidationResult(
            False, "不可出牌（playable=false）的牌不应有即时词缀"
        )

    split = _split_affix(affix)
    if split is None:
        return AffixValidationResult(
            False, "词缀缺少 `[名称]:` 分隔，无法拆分名称与机械描述"
        )
    name, desc = split
    if not name:
        return AffixValidationResult(False, "词缀名为空")
    if not desc:
        return AffixValidationResult(False, "机械结算描述为空")
    if "词缀名" in name or "何种" in desc or "待设计" in desc:
        return AffixValidationResult(False, "仍是占位符，请替换为具体设计")

    # 字段锚点：涉及某类语义时必须显式写出对应字段名。
    if any(word in desc for word in _DAMAGE_WORDS) and "damage" not in desc:
        return AffixValidationResult(False, "涉及伤害必须显式引用 `damage` 字段")
    if any(word in desc for word in _BLOCK_WORDS) and "block" not in desc:
        return AffixValidationResult(False, "涉及格挡/防御必须显式引用 `block` 字段")
    if card.transferable and any(word in desc for word in _HOLDER_WORDS):
        if "source" not in desc:
            return AffixValidationResult(
                False, "可转移牌涉及持有者必须显式引用 `source` / 非 source 者"
            )

    # 数值限制：只允许 `字段×N`，且 N 在护栏内；其余数字一律视为独立数值。
    limits = _MAX_MULTIPLIERS[affix_field]
    for match in _MULTIPLIER_RE.finditer(desc):
        field_name, raw_n = match.group(1), match.group(2)
        limit = limits.get(field_name)
        if limit is None:
            return AffixValidationResult(
                False, f"{affix_field} 不允许引用 `{field_name}` 倍率"
            )
        n = int(raw_n)
        if n < 1 or n > limit:
            return AffixValidationResult(
                False, f"`{field_name}×{n}` 超出本时机护栏上限 {limit}"
            )

    scrubbed = _MULTIPLIER_RE.sub("", desc)
    if _DIGIT_RE.search(scrubbed):
        return AffixValidationResult(
            False, "出现独立数值：只允许引用字段并附护栏内倍率（如 `本卡 damage×2`）"
        )

    return AffixValidationResult(True)


#######################################################################################################################################
def apply_affix_design(
    entity_name: str,
    card: Card,
    submitted: Mapping[str, Optional[List[str]]],
) -> Tuple[int, List[str]]:
    """应用 agent 设计的词缀；任一槽校验失败则整槽回退原型。

    `submitted` 为「字段名 → 设计后的词缀列表」；值为 None 表示该槽未提交（保留原型）。
    返回 (成功应用的词缀条数, 回退原因列表)。
    """
    applied = 0
    fallbacks: List[str] = []

    for affix_field in AFFIX_FIELDS:
        affix_list = submitted.get(affix_field)
        if affix_list is None:
            continue

        original: List[str] = list(getattr(card, affix_field))
        if not original:
            if affix_list:
                fallbacks.append(f"{affix_field}: 原型该槽为空，忽略设计提交")
            continue

        if not affix_list:
            fallbacks.append(f"{affix_field}: 设计为空，整槽回退原型")
            continue

        for affix in affix_list:
            result = validate_affix_slot(affix_field, affix, card)
            if not result.ok:
                fallbacks.append(
                    f"{affix_field}: {result.reason}（{entity_name} 卡「{card.name}」整槽回退原型）"
                )
                break
        else:
            setattr(card, affix_field, [a.strip() for a in affix_list])
            applied += len(affix_list)

    return applied, fallbacks
