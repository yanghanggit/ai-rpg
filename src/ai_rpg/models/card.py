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

词缀是你为角色设计的**增益 / 减益规则**，由仲裁 LLM 直接执行。每个词缀槽是**多值列表**：一个元素＝一条完整词缀，禁止拆分或合并；无词缀时留空。

### 一、结算原语（效果的硬边界）

仲裁的读写面只有：

- **读**：`HP` / 最大 `HP`、总格挡（角色级＝其手牌 `block` 之和）、**获取状态的工具**返回的带 `on_hit_affixes` 手牌（含 `source` / `damage` / `hit_count` / `block` / 词缀）。
- **写**：只有 `HP`——**格挡不能写入**（`block×N` 只用来算伤害 / 代价，不能授予格挡）。

由此，可用的效果只有两类：

- **伤害**：写 `HP`，数值由本卡 `damage` / `hit_count` 与目标的总格挡算出。
- **持续状态**：无独立状态存储——角色「状态」＝其手牌中承载词缀的牌。要施加持续状态（含 `本回合内` / `持续 N 回合` / `直到…` 这类时间修饰），就设计 `transferable=True` 的牌投进对方手牌，由牌自带的词缀持续结算。

以下都不属于词缀，写进词缀也不会生效：抽牌 / 弃牌 / 移牌（把牌置入、投进或收回手牌）/ 能量（回能）/ 额外行动、改 `playable` / `exhaust` / `retain` / `ethereal` / `transferable`、无牌承载的标记（「叠加 X 层」）。其余范围外的效果一律不被结算，请改写或删除。

### 二、三个时机

- `on_play_affixes`：本卡打出时结算，仅本次出牌生效。
- `on_hit_affixes`：本卡持有者被本次出牌命中时触发。
- `on_turn_end_affixes`：持有者每次 pass turn 结算一次（只结算其本人手牌中带该词缀的牌）。

### 三、书写约定与数值限制

- **格式（硬要求）**：`[词缀名]:机械结算描述`。`[` `]` 是必须原样写出的字面字符（不是占位符），与分隔符同样缺一不可（客户端按 `[名称]:说明` 解析），词缀名可自由创造；写成 `名:描述` 判不合法，**整槽置空**。
- **可引用的内建数值**（仲裁阶段会全量给出，只能引用、不能写回；优先用它们，别写死具体数字）：本卡 `damage` / `block` / `hit_count`；目标 `HP` / 最大 `HP` / 总格挡；自身 `HP` / 总格挡。取数要写明：伤害用 `damage`（如 `本卡 damage×2`）或目标内建值；治疗写「回复 HP」；格挡写 `block`；段数写 `hit_count`——**别只写「结算」**（仲裁要知道是伤害还是回复）。
- **`×N` 上限**：`on_play` `damage×1..3` / `block×1..3` / `hit_count×1..2`；`on_hit` `damage×1..3` / `block×1..3`；`on_turn_end` `damage×1..2` / `block×1..3`。
- **作用对象**只用这些称谓：`自身` / `出牌者` / `目标` / `本卡持有者` / `非 source 者`（＝持有者，且持有者 ≠ 本卡 `source`）；`on_turn_end_affixes` 无「出牌者 / 目标」，只能用 `自身` / `本卡持有者` / `非 source 者` / 场上存活角色。
- 本卡 `damage=0` 时不得凭空造成伤害。
"""

#######################################################################################################################################
BUILD_CARD_FIELD_DESCRIPTION: Final[
    str
] = f"""## 卡牌字段语义

卡牌是战斗行动的最小单元：确定性骨架字段决定回合循环，语义词缀承载设计。

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
| `block` | 手牌持有期间提供的格挡，累加进持有者的有效防御；默认 0 |
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
    """校验一条 agent 设计的词缀是否满足**硬不变量**。

    只守计算端必须保证的东西：时机 schema、多值格式、非空、占位符、
    倍率护栏（`字段×N` 的 N 上限）、时机与骨架 flag 的一致性。
    语义是否「可被仲裁结算」不在这里用正则猜——它由「结算原语」契约与
    agent 提交前自检负责（见 `AFFIX_DESIGN_SPEC`）。
    """
    if affix_field not in _MAX_MULTIPLIERS:
        return AffixValidationResult(False, f"未知词缀时机 {affix_field!r}")

    if affix_field == "on_play_affixes" and not card.playable:
        return AffixValidationResult(
            False, "不可出牌（playable=false）的牌不应有即时词缀"
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

    # 倍率护栏：`字段×N` 的 N 需在本时机的上限内（独立数字不再拦截）。
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

    return AffixValidationResult(True)


#######################################################################################################################################
def apply_affix_design(
    entity_name: str,
    card: Card,
    submitted: Mapping[str, Optional[List[str]]],
) -> Tuple[int, List[str]]:
    """把 agent 设计的词缀应用到 `card` 上，返回 (成功应用的条数, 说明列表)。

    槽位语义（方法论：定量骨架 + 变量词缀）：
    - 原型中**非空**的词缀槽是「**引导**」，只用来标记该槽可设计，**不是**回退答案；
    - 该槽最终值只取 agent 的**合法**提交；未提交 / 设计为空 / 不合法，一律**置空**；
    - 原型为空的槽不是可设计槽，任何提交都被忽略。

    `submitted` 为「字段名 → 设计后的词缀列表」。
    """
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
    """把 agent 提交的骨架数值微调覆盖到 `card` 上（`None` 表示沿用原型）。

    骨架数值（`cost` / `damage` / `hit_count` / `block`）不加护栏：agent 自己把握，
    计算端只保证类型可解析。布尔与目标字段不在可调范围。
    """
    if cost is not None:
        card.cost = cost
    if damage is not None:
        card.damage = damage
    if hit_count is not None:
        card.hit_count = hit_count
    if block is not None:
        card.block = block
