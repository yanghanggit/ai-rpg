"""卡牌原型注册表

本文件创建「卡牌原型」：与游戏内容完全解耦的指导性卡牌，供 Agent 工具检索时
作为上下文引导。原型复用 `Card` 模型，但 `name` / `description` 均为教学性文本，
不指向任何具体故事、角色或牌名。

每个原型在底部注册表中附带元数据，支持**逐级披露**：
  - 一级（列表 / 检索）：返回 `meta.name` + `meta.summary` + `meta.tags`；
  - 二级（展开）：返回 `Card` 的完整字段与 `meta.guide` 完整设计指导。

`meta.archetype` 区分原型来源：`攻击` / `防御` 为基础卡牌原型，`装备` 为装备物化
卡牌原型（供工坊合成「选择核心 + 润色」检索）。后续新增原型时，在下方追加全局
实例并登记到 `CARD_PROTOTYPES` 即可。
"""

from dataclasses import dataclass
from typing import Final, List, Tuple

from ai_rpg.models import Card, TargetType


@dataclass(frozen=True)
class CardPrototypeMeta:
    """卡牌原型的检索元数据。"""

    prototype_id: str  # 稳定检索键，工具据此定位原型
    archetype: str  # 原型来源 / 类别标签（攻击 / 防御 / 装备）
    name: str  # 索引展示名（教学性文本）
    summary: str  # 一级披露：一句话摘要，供列表与检索
    guide: str  # 二级披露：完整字段语义与设计指导，供展开
    tags: Tuple[str, ...] = ()  # 检索标签（装备原型带「装备」标记 + 机制标签）


@dataclass(frozen=True)
class CardPrototype:
    """一个已注册的卡牌原型 = 原型 Card + 检索元数据。"""

    card: Card
    meta: CardPrototypeMeta


# ── 基础卡牌原型 ──────────────────────────────────────────────

ATTACK_PROTOTYPE: Final[Card] = Card(
    name="基础攻击",
    description="单目标直接伤害原型：费用 1，伤害为卡牌自身值，填充牌库时叠加角色攻击力。",
    on_play_affixes=[],
    on_hit_affixes=[],
    on_turn_end_affixes=[],
    playable=True,
    exhaust=False,
    retain=False,
    ethereal=False,
    transferable=False,
    cost=1,
    damage=1,
    hit_count=1,
    block=0,
    target_type=TargetType.SINGLE,
    self_target=False,
)


DEFENSE_PROTOTYPE: Final[Card] = Card(
    name="基础防御",
    description="自身格挡原型：费用 1，格挡为卡牌自身值，填充牌库时叠加角色防御力，持有期间计入持有者总防御。",
    on_play_affixes=[],
    on_hit_affixes=[],
    on_turn_end_affixes=[],
    playable=True,
    exhaust=False,
    retain=False,
    ethereal=False,
    transferable=False,
    cost=1,
    damage=0,
    hit_count=1,
    block=2,
    target_type=TargetType.SINGLE,
    self_target=True,
)


# ── 装备卡牌原型（工坊合成「选择核心 + 润色」用） ──────────────

GEAR_OFFENSE_PROTOTYPE: Final[Card] = Card(
    name="装备.名字",
    description="对装备进行描述，突出装备特点",
    on_play_affixes=["[词缀名]:本次出牌产生何种即时效果"],
    on_hit_affixes=[],
    on_turn_end_affixes=[],
    playable=True,
    exhaust=False,
    retain=False,
    ethereal=False,
    transferable=False,
    cost=1,
    damage=3,
    hit_count=1,
    block=0,
    target_type=TargetType.SINGLE,
    self_target=False,
)


GEAR_DEFENSE_PROTOTYPE: Final[Card] = Card(
    name="装备.名字",
    description="对装备进行描述，突出装备特点",
    on_play_affixes=[],
    on_hit_affixes=["[词缀名]:持有者受到攻击命中时触发何种效果"],
    on_turn_end_affixes=[],
    playable=True,
    exhaust=False,
    retain=True,
    ethereal=False,
    transferable=False,
    cost=1,
    damage=0,
    hit_count=1,
    block=3,
    target_type=TargetType.SINGLE,
    self_target=False,
)


GEAR_CONTAGION_PROTOTYPE: Final[Card] = Card(
    name="装备.名字",
    description="对装备进行描述，突出装备特点",
    on_play_affixes=[],
    on_hit_affixes=[],
    on_turn_end_affixes=["[词缀名]:回合结束时对非 source 者结算何种持续效果"],
    playable=True,
    exhaust=False,
    retain=True,
    ethereal=False,
    transferable=True,
    cost=1,
    damage=1,
    hit_count=1,
    block=0,
    target_type=TargetType.SINGLE,
    self_target=False,
)


# ── 注册表 ──────────────────────────────────────────────────────────

CARD_PROTOTYPES: Final[List[CardPrototype]] = [
    CardPrototype(
        card=ATTACK_PROTOTYPE,
        meta=CardPrototypeMeta(
            prototype_id="proto.attack",
            archetype="攻击",
            name="基础攻击",
            summary="单目标直接伤害，最低成本的输出基线。",
            guide=(
                "字段：target_type=SINGLE、self_target=False、damage=1、hit_count=1、"
                "block=0、cost=1。填充牌库时 damage 叠加角色攻击力；block 为 0，不承担防御。"
                "设计指引：作为输出卡原型，变体在其上叠加词缀（穿甲/多段）或流转标志"
                "（exhaust/ethereal）以创造差异化。"
            ),
            tags=(),
        ),
    ),
    CardPrototype(
        card=DEFENSE_PROTOTYPE,
        meta=CardPrototypeMeta(
            prototype_id="proto.defense",
            archetype="防御",
            name="基础防御",
            summary="为自身提供格挡，持有期间提升防御。",
            guide=(
                "字段：self_target=True（忽略 target_type）、damage=0、block=2、cost=1。"
                "填充牌库时 block 叠加角色防御力；持有期间计入持有者总防御，与是否打出无关。"
                "设计指引：作为防御卡原型，变体在其上叠加 retain（常驻）、受击词缀（反伤/减伤）"
                "以创造差异化。"
            ),
            tags=(),
        ),
    ),
    CardPrototype(
        card=GEAR_OFFENSE_PROTOTYPE,
        meta=CardPrototypeMeta(
            prototype_id="gear.offense",
            archetype="装备",
            name="进攻装备",
            summary="出牌即时造成伤害，词缀集中在 on_play_affixes。",
            guide=(
                "字段：target_type=SINGLE、self_target=False、damage=3、hit_count=1、"
                "block=0、cost=1。即时词缀承载出牌伤害，伤害随填充叠加角色攻击力。"
                "润色：把即时词缀替换为具体效果，name/description 由系统沿用装备的。"
            ),
            tags=("装备", "on_play_affixes", "damage"),
        ),
    ),
    CardPrototype(
        card=GEAR_DEFENSE_PROTOTYPE,
        meta=CardPrototypeMeta(
            prototype_id="gear.defense",
            archetype="装备",
            name="防御装备",
            summary="持有期提供格挡，受击时触发词缀，跨回合保留。",
            guide=(
                "字段：self_target=False、damage=0、block=3、cost=1、retain=True。"
                "持有期提供格挡（计入总防御），受击词缀触发反制，retain 跨回合保留。"
                "润色：把受击词缀替换为具体反制效果，name/description 由系统沿用装备的。"
            ),
            tags=("装备", "on_hit_affixes", "block", "retain"),
        ),
    ),
    CardPrototype(
        card=GEAR_CONTAGION_PROTOTYPE,
        meta=CardPrototypeMeta(
            prototype_id="gear.contagion",
            archetype="装备",
            name="投掷/传染装备",
            summary="出牌后转移给敌人，回合结束对非 source 者持续结算。",
            guide=(
                "字段：transferable=True、retain=True、damage=1、hit_count=1、"
                "block=0、target_type=SINGLE。出牌后转移到目标手牌，回合结束词缀对非 source 者"
                "持续结算。润色：把回合结束词缀替换为具体持续效果，name/description 由系统沿用装备的。"
            ),
            tags=("装备", "transferable", "on_turn_end_affixes", "retain"),
        ),
    ),
]
