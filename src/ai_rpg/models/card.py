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
AFFIX_DESIGN_SPEC: Final[
    str
] = """## 词缀设计规范

词缀是你为角色设计的**增益 / 减益规则**，由仲裁 LLM 直接执行。每个词缀槽是**多值列表**：一个元素＝一条完整词缀，禁止拆分或合并；无词缀时留空。

### 一、结算原语（效果的硬边界）

- **读**：`HP` / 最大 `HP`、总格挡（其手牌 `block` 之和）、**获取状态的工具**返回的带 `on_hit_affixes` 手牌（含 `source` / `damage` / `hit_count` / `block` / 词缀）。
- **写**：只有 `HP`——**格挡不能写入**（`block` 只用来算伤害 / 代价）。

可结算的效果只有（都只写 `HP`）：

- **伤害**：目标 `HP −= max(0, base × 伤害系数 − 目标总格挡 × 格挡系数)`，逐段求和（`base` 取本卡 `damage` 或文案明示的内建值）。
- **反伤 / 吸血 / 治疗**：反伤＝被命中时对攻击方写 `HP`（不过格挡）；吸血 / 治疗＝对自身 / 目标回复 `HP`；每段一次。
- **持续状态**：无独立状态存储——角色「状态」＝其手牌中承载词缀的牌。要施加持续状态，就设计 `transferable=True` 的牌投进对方手牌，由牌自带词缀持续结算。

以下写进词缀也不生效：抽牌 / 弃牌 / 移牌 / 能量 / 额外行动、改 `playable` / `exhaust` / `retain` / `ethereal` / `transferable`、无牌承载的标记；范围外一律不结算（记入 `unsettled_affixes`），请改写或删除。

### 二、四个时机

- `on_play_affixes`：本卡打出时结算，仅本次出牌生效。
- `on_hit_affixes`：本卡持有者被本次出牌命中时触发。
- `on_turn_end_affixes`：持有者每次 pass turn 对**当前持有者本人**结算一次（只结算其本人手牌中带该词缀的牌）；目标恒为持有者，`hit_count` 即对其结算段数。
- `on_autonomous_affixes`：持有者每次 pass turn（在 `on_turn_end_affixes` **之后**）结算，只结算持有者本人手牌中带该词缀的牌。与前三者的根本区别：**效果目标为场上任意存活角色**，不限于持有者，目标由词缀文本指定；其造成的伤害**算命中**，会触发被命中者的受击词缀。

### 三、书写约定

- **格式（硬要求）**：`[词缀名]:机械结算描述`（`[` `]` 与分隔符缺一不可；客户端按 `[名称]:说明` 解析）。写成 `名:描述` 判不合法，**整槽置空**。
- **取数**（仲裁会全量给出，只能引用、不能写回；优先用内建值）：本卡 `damage` / `block` / `hit_count`；目标 / 自身的 `HP` / 最大 `HP` / 总格挡。写明伤害（`damage`）还是回复（`HP`）、段数（`hit_count`）还是格挡（`block`），**别只写「结算」**。
- **作用对象**：`自身` / `出牌者` / `目标` / `本卡持有者` / `source 者`（持有者 == `source`）/ `非 source 者`（持有者 ≠ `source`）。`on_turn_end` 目标恒为持有者，只允许 `自身` / `本卡持有者` / `source 者` / `非 source 者`——前两者无条件，后两者按持有者与 `source` 的关系决定是否结算；不得指向其他角色。`on_autonomous_affixes` 可指向场上**任意存活角色**，必须在描述中写明目标如何选取。
- **source 门控**：`source`＝本卡来源（生成 / 注入者），`transferable` 副本保留原 `source` 但落地即 `transferable=False`（只传一跳，不可再传递）。`非 source 者` 只伤外人（投毒牌不反噬原主），`source 者` 只利原主。例：`[反噬]:回合结束时对非 source 者造成本卡 damage 的伤害`。
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
| `transferable` | 出牌时额外为每个目标手牌 copy 一份（副本 `transferable` 置 false、不可再传递；本体照常结算并进入弃牌/消耗流程）；默认 false |
| `cost` | 出牌费用（消耗 energy）；默认 1 |
| `damage` | 单次伤害；默认 0 |
| `hit_count` | 攻击次数，多段各自独立结算；默认 1 |
| `block` | 手牌持有期间提供的格挡，累加进持有者的有效防御；默认 0 |
| `target_type` | 目标类型（见下表） |

### 布尔标志的互斥与依赖

- `retain` 与 `ethereal` 互斥，禁止同时为 true：二者同属「回合边界手中牌去向」的两极，同时开启时 ethereal（pass turn 即消耗）先于 retain（回合末保留）生效，retain 失效。
- `transferable` 与 `exhaust` 均为「被打出时」结算，故为 true 时要求 `playable=true`；`playable=false` 时牌不可出，二者永不触发，属无效组合。
- `target_type=SELF` 可与 `transferable` 同开：`SELF` 解析出的目标即出牌者本人，`transferable` 会把副本复制回自己手牌，即「自传递复制」。
- `transferable` 只传递一跳：副本落地到目标手牌时系统把其 `transferable` 置为 false，收到副本者不能再次转手（链式传递与自传递回收均被关闭）；副本仍保留原 `source` 与词缀，持续结算不受影响。
- `ethereal` 与 `on_autonomous_affixes` 互斥，禁止同时出现：`ethereal` 会在 pass turn 时先于自主运行阶段把牌移入 ExhaustPile，自主词缀永不触发，属无效组合（校验会拒绝该组合）。

### 目标类型（target_type）

| 值 | 含义 |
| --- | --- |
| `{TargetType.SINGLE}` | 单个存活角色（默认），需显式传入 1 个锚点 |
| `{TargetType.ALL}` | 阵营锚点：以指定目标为锚点，作用于其所在阵营（我方/敌方）的全部存活角色 |
| `{TargetType.SPREAD}` | 阵营锚点：散射锚点所在阵营的存活角色；hit_count 超过人数时每人至少一次，多余随机；否则纯随机 |
| `{TargetType.SELF}` | 锁定出牌者自身；无需 targets，传入的目标列表被忽略 |

### source

`source` 记录牌来源（生成/注入者）名称，由系统填充，无需输出；`transferable` 的副本保留原 `source`。词缀可用 `source 者` / `非 source 者` 按持有者与 `source` 的关系设生效条件，实现「投给他人后才生效 / 只有原主生效」等玩法。"""


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
