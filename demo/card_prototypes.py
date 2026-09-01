"""卡牌原型注册表

本文件创建「卡牌原型」：与游戏内容完全解耦的指导性卡牌，供 Agent 工具检索时
作为上下文引导。原型复用 `Card` 模型，但 `name` / `description` 均为教学性文本，
不指向任何具体故事、角色或牌名。

每个原型在底部注册表中附带元数据，支持**逐级披露**：
  - 一级（列表 / 检索）：返回 `meta.name` + `meta.summary` + `meta.tags`；
  - 二级（展开）：返回 `Card` 的完整字段与 `meta.guide` 完整设计指导。

分类采用「三端化思维」，每项元数据标注两个维度：
  - `domain`：应用场景（`手牌` / `装备`）；
  - `port` + `port_subtype`：三端大类与小类（攻击端 / 防御端；运转端暂无字段，
    不进入原型）。

小类词汇见「三端化思维」文档：
  - 攻击端：前端伤害 / 成长性伤害 / 铺垫性攻击支持
  - 防御端：前端防御 / 成长性防御 / 特殊防御机制

后续新增原型时，在下方追加全局实例并登记到 `CARD_PROTOTYPES` 即可。
"""

from dataclasses import dataclass
from typing import Final, List, Tuple

from ai_rpg.models import Card, TargetType


@dataclass(frozen=True)
class CardPrototypeMeta:
    """卡牌原型的检索元数据。"""

    prototype_id: str  # 稳定检索键，工具据此定位原型
    domain: str  # 应用场景：手牌 / 装备
    port: str  # 三端大类：攻击端 / 防御端 / 运转端
    port_subtype: str  # 三端小类（见模块 docstring）
    name: str  # 索引展示名（教学性文本）
    summary: str  # 一级披露：一句话摘要，供列表与检索
    guide: str  # 二级披露：完整字段语义与设计指导，供展开
    tags: Tuple[str, ...] = ()  # 检索标签（关键字段名）


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


# ── 攻击端原型 ──────────────────────────────────────────────

BURST_PROTOTYPE: Final[Card] = Card(
    name="一次性爆发",
    description="高费用单次高伤，打出后永久消耗，整场只此一次。",
    on_play_affixes=[],
    on_hit_affixes=[],
    on_turn_end_affixes=[],
    playable=True,
    exhaust=True,
    retain=False,
    ethereal=False,
    transferable=False,
    cost=3,
    damage=6,
    hit_count=1,
    block=0,
    target_type=TargetType.SINGLE,
    self_target=False,
)


SACRIFICE_PROTOTYPE: Final[Card] = Card(
    name="代价爆发",
    description="高伤但打出时反噬自身。",
    on_play_affixes=["[自损]:打出时对自己造成伤害"],
    on_hit_affixes=[],
    on_turn_end_affixes=[],
    playable=True,
    exhaust=True,
    retain=False,
    ethereal=False,
    transferable=False,
    cost=2,
    damage=5,
    hit_count=1,
    block=0,
    target_type=TargetType.SINGLE,
    self_target=False,
)


FOCUS_PROTOTYPE: Final[Card] = Card(
    name="集火连击",
    description="对单体多段独立结算的连击。",
    on_play_affixes=[],
    on_hit_affixes=[],
    on_turn_end_affixes=[],
    playable=True,
    exhaust=False,
    retain=False,
    ethereal=False,
    transferable=False,
    cost=2,
    damage=2,
    hit_count=3,
    block=0,
    target_type=TargetType.SINGLE,
    self_target=False,
)


SPREAD_PROTOTYPE: Final[Card] = Card(
    name="散射清场",
    description="多段伤害在敌阵营内散射分配。",
    on_play_affixes=[],
    on_hit_affixes=[],
    on_turn_end_affixes=[],
    playable=True,
    exhaust=False,
    retain=False,
    ethereal=False,
    transferable=False,
    cost=2,
    damage=1,
    hit_count=4,
    block=0,
    target_type=TargetType.SPREAD,
    self_target=False,
)


MARK_PROTOTYPE: Final[Card] = Card(
    name="传染标记",
    description="打出后把负面标记转嫁给目标手牌，被命中时反受其害。",
    on_play_affixes=[],
    on_hit_affixes=["[标记]:被命中时承受额外伤害"],
    on_turn_end_affixes=[],
    playable=True,
    exhaust=False,
    retain=False,
    ethereal=False,
    transferable=True,
    cost=1,
    damage=0,
    hit_count=1,
    block=0,
    target_type=TargetType.SINGLE,
    self_target=False,
)


PIERCE_PROTOTYPE: Final[Card] = Card(
    name="破甲输出",
    description="本次伤害无视目标防御。",
    on_play_affixes=["[穿甲]:本次伤害无视目标防御"],
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


SELF_LOOP_PROTOTYPE: Final[Card] = Card(
    name="自我循环",
    description="锁定自身，每回合给自己叠增益。",
    on_play_affixes=[],
    on_hit_affixes=[],
    on_turn_end_affixes=["[循环]:回合结束时自身获益"],
    playable=True,
    exhaust=False,
    retain=True,
    ethereal=False,
    transferable=False,
    cost=1,
    damage=0,
    hit_count=1,
    block=0,
    target_type=TargetType.SINGLE,
    self_target=True,
)


FLEETING_PROTOTYPE: Final[Card] = Card(
    name="限时机会",
    description="限时强力，本回合不用即消失。",
    on_play_affixes=["[爆发]:本次出牌额外收益"],
    on_hit_affixes=[],
    on_turn_end_affixes=[],
    playable=True,
    exhaust=False,
    retain=False,
    ethereal=True,
    transferable=False,
    cost=1,
    damage=2,
    hit_count=1,
    block=0,
    target_type=TargetType.SINGLE,
    self_target=False,
)


DOT_PROTOTYPE: Final[Card] = Card(
    name="持续减益传染",
    description="打出后转嫁给目标，每回合末持续受损。",
    on_play_affixes=[],
    on_hit_affixes=[],
    on_turn_end_affixes=["[中毒]:回合结束时对非 source 者结算持续伤害"],
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


AOE_PROTOTYPE: Final[Card] = Card(
    name="群体打击",
    description="对敌阵营全体造成伤害。",
    on_play_affixes=[],
    on_hit_affixes=[],
    on_turn_end_affixes=[],
    playable=True,
    exhaust=False,
    retain=False,
    ethereal=False,
    transferable=False,
    cost=2,
    damage=2,
    hit_count=1,
    block=0,
    target_type=TargetType.ALL,
    self_target=False,
)


AOE_DEBUFF_PROTOTYPE: Final[Card] = Card(
    name="群体减益",
    description="对敌阵营全体施加减益。",
    on_play_affixes=["[诅咒]:本次出牌对目标阵营施加减益"],
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
    block=0,
    target_type=TargetType.ALL,
    self_target=False,
)


# ── 防御端原型 ──────────────────────────────────────────────

BULWARK_PROTOTYPE: Final[Card] = Card(
    name="防御蓄力",
    description="持有期格挡，跨回合保留。",
    on_play_affixes=[],
    on_hit_affixes=[],
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
    self_target=True,
)


THORNS_PROTOTYPE: Final[Card] = Card(
    name="反伤壁垒",
    description="持牌高防，被命中时反制攻击者。",
    on_play_affixes=[],
    on_hit_affixes=["[反伤]:被命中时对出牌者造成伤害"],
    on_turn_end_affixes=[],
    playable=True,
    exhaust=False,
    retain=True,
    ethereal=False,
    transferable=False,
    cost=1,
    damage=2,
    hit_count=1,
    block=2,
    target_type=TargetType.SINGLE,
    self_target=True,
)


PASSIVE_PROTOTYPE: Final[Card] = Card(
    name="常驻被动",
    description="不可打出，跨回合持有，每回合末结算持续效果。",
    on_play_affixes=[],
    on_hit_affixes=[],
    on_turn_end_affixes=["[常驻]:回合结束时结算持续效果"],
    playable=False,
    exhaust=False,
    retain=True,
    ethereal=False,
    transferable=False,
    cost=1,
    damage=0,
    hit_count=1,
    block=0,
    target_type=TargetType.SINGLE,
    self_target=True,
)


SUPPORT_PROTOTYPE: Final[Card] = Card(
    name="支援分发",
    description="打出后把增益副本分发给队友。",
    on_play_affixes=[],
    on_hit_affixes=[],
    on_turn_end_affixes=["[增益]:回合结束时持有者获益"],
    playable=True,
    exhaust=False,
    retain=False,
    ethereal=False,
    transferable=True,
    cost=1,
    damage=0,
    hit_count=1,
    block=0,
    target_type=TargetType.SINGLE,
    self_target=False,
)


AOE_BUFF_PROTOTYPE: Final[Card] = Card(
    name="群体增益",
    description="对己方阵营全体施加增益。",
    on_play_affixes=[],
    on_hit_affixes=[],
    on_turn_end_affixes=["[增益]:回合结束时持有者获益"],
    playable=True,
    exhaust=False,
    retain=False,
    ethereal=False,
    transferable=False,
    cost=1,
    damage=0,
    hit_count=1,
    block=0,
    target_type=TargetType.ALL,
    self_target=False,
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
    # 手牌 / 攻击端 / 前端伤害
    CardPrototype(
        card=ATTACK_PROTOTYPE,
        meta=CardPrototypeMeta(
            prototype_id="proto.attack",
            domain="手牌",
            port="攻击端",
            port_subtype="前端伤害",
            name="基础攻击",
            summary="单目标直接伤害，最低成本的输出基线。",
            guide=(
                "字段：target_type=SINGLE、self_target=False、damage=1、hit_count=1、"
                "block=0、cost=1。填充牌库时 damage 叠加角色攻击力；block 为 0，不承担防御。"
                "设计指引：作为输出卡原型，变体在其上叠加词缀（穿甲/多段）或流转标志"
                "（exhaust/ethereal）以创造差异化。"
            ),
            tags=("damage", "single"),
        ),
    ),
    CardPrototype(
        card=BURST_PROTOTYPE,
        meta=CardPrototypeMeta(
            prototype_id="proto.burst",
            domain="手牌",
            port="攻击端",
            port_subtype="前端伤害",
            name="一次性爆发",
            summary="高费高伤 + 消耗，整场只此一次。",
            guide=(
                "字段：cost=3、damage=6、exhaust=True、SINGLE。整场只结算一次，"
                "允许效果明显超模，制造「何时出手」的时机抉择。"
            ),
            tags=("exhaust", "damage", "cost"),
        ),
    ),
    CardPrototype(
        card=SACRIFICE_PROTOTYPE,
        meta=CardPrototypeMeta(
            prototype_id="proto.sacrifice",
            domain="手牌",
            port="攻击端",
            port_subtype="前端伤害",
            name="代价爆发",
            summary="高伤 + 自伤代价，一次性爆发。",
            guide=(
                "字段：damage=5、exhaust=True、on_play_affixes=[自损]。"
                "用即时词缀（减益）支付代价换取超模输出，高风险高回报。"
            ),
            tags=("exhaust", "damage", "on_play_affixes"),
        ),
    ),
    CardPrototype(
        card=FOCUS_PROTOTYPE,
        meta=CardPrototypeMeta(
            prototype_id="proto.focus",
            domain="手牌",
            port="攻击端",
            port_subtype="前端伤害",
            name="集火连击",
            summary="单体多段爆发。",
            guide=(
                "字段：SINGLE、hit_count=3、damage=2。多段各自独立结算，集火单个目标。"
            ),
            tags=("hit_count", "damage", "single"),
        ),
    ),
    CardPrototype(
        card=SPREAD_PROTOTYPE,
        meta=CardPrototypeMeta(
            prototype_id="proto.spread",
            domain="手牌",
            port="攻击端",
            port_subtype="前端伤害",
            name="散射清场",
            summary="多段散射，不精确扩散。",
            guide=(
                "字段：SPREAD、hit_count=4。段数在敌阵营内随机或保底分配，适合清场。"
            ),
            tags=("spread", "hit_count"),
        ),
    ),
    CardPrototype(
        card=PIERCE_PROTOTYPE,
        meta=CardPrototypeMeta(
            prototype_id="proto.pierce",
            domain="手牌",
            port="攻击端",
            port_subtype="前端伤害",
            name="破甲输出",
            summary="即时词缀（增益）让本次伤害穿透防御。",
            guide=(
                "字段：on_play_affixes=[穿甲]、SINGLE。即时词缀（增益）直接增强本次出牌伤害，"
                "无视目标防御。"
            ),
            tags=("on_play_affixes", "damage", "single"),
        ),
    ),
    CardPrototype(
        card=FLEETING_PROTOTYPE,
        meta=CardPrototypeMeta(
            prototype_id="proto.fleeting",
            domain="手牌",
            port="攻击端",
            port_subtype="前端伤害",
            name="限时机会",
            summary="虚无 + 高收益，不用即消失。",
            guide=(
                "字段：ethereal=True、damage=2、on_play_affixes=[爆发]。"
                "限时兑现压力，逼玩家当回合决定用或弃。"
            ),
            tags=("ethereal", "on_play_affixes"),
        ),
    ),
    CardPrototype(
        card=AOE_PROTOTYPE,
        meta=CardPrototypeMeta(
            prototype_id="proto.aoe",
            domain="手牌",
            port="攻击端",
            port_subtype="前端伤害",
            name="群体打击",
            summary="ALL + 伤害，群体打击。",
            guide=("字段：ALL、damage=2。以目标为锚点，作用于其所在阵营全体。"),
            tags=("all", "damage"),
        ),
    ),
    # 手牌 / 攻击端 / 成长性伤害
    CardPrototype(
        card=DOT_PROTOTYPE,
        meta=CardPrototypeMeta(
            prototype_id="proto.dot",
            domain="手牌",
            port="攻击端",
            port_subtype="成长性伤害",
            name="持续减益传染",
            summary="转嫁 + 回合末持续减益。",
            guide=(
                "字段：transferable=True、retain=True、on_turn_end_affixes=[中毒]。"
                "副本落在目标手牌，每回合末对非 source 者持续结算。"
            ),
            tags=("transferable", "retain", "on_turn_end_affixes"),
        ),
    ),
    # 手牌 / 攻击端 / 铺垫性攻击支持
    CardPrototype(
        card=MARK_PROTOTYPE,
        meta=CardPrototypeMeta(
            prototype_id="proto.mark",
            domain="手牌",
            port="攻击端",
            port_subtype="铺垫性攻击支持",
            name="传染标记",
            summary="把受击减益转嫁给敌人，可再被即时词缀引爆。",
            guide=(
                "字段：transferable=True、on_hit_affixes=[标记]。副本进入目标手牌并保留 source，"
                "配合「非 source 者」反噬，或后续用即时词缀针对该减益收割。"
            ),
            tags=("transferable", "on_hit_affixes"),
        ),
    ),
    CardPrototype(
        card=SELF_LOOP_PROTOTYPE,
        meta=CardPrototypeMeta(
            prototype_id="proto.selfloop",
            domain="手牌",
            port="攻击端",
            port_subtype="铺垫性攻击支持",
            name="自我循环",
            summary="锁定自身 + 保留，每回合叠增益。",
            guide=(
                "字段：self_target=True、retain=True、on_turn_end_affixes=[循环]。"
                "每回合给自己叠状态，为后续输出/防御做铺垫。"
            ),
            tags=("self_target", "retain", "on_turn_end_affixes"),
        ),
    ),
    CardPrototype(
        card=AOE_DEBUFF_PROTOTYPE,
        meta=CardPrototypeMeta(
            prototype_id="proto.aoe_debuff",
            domain="手牌",
            port="攻击端",
            port_subtype="铺垫性攻击支持",
            name="群体减益",
            summary="ALL + 敌阵营，群体减益。",
            guide=(
                "字段：ALL + 敌阵营锚点 + 即时词缀（减益）。一轮给整队挂负面，"
                "为后续伤害做铺垫。"
            ),
            tags=("all", "on_play_affixes"),
        ),
    ),
    # 手牌 / 防御端 / 前端防御
    CardPrototype(
        card=DEFENSE_PROTOTYPE,
        meta=CardPrototypeMeta(
            prototype_id="proto.defense",
            domain="手牌",
            port="防御端",
            port_subtype="前端防御",
            name="基础防御",
            summary="为自身提供格挡，持有期间提升防御。",
            guide=(
                "字段：self_target=True（忽略 target_type）、damage=0、block=2、cost=1。"
                "填充牌库时 block 叠加角色防御力；持有期间计入持有者总防御，与是否打出无关。"
                "设计指引：作为防御卡原型，变体在其上叠加 retain（常驻）、受击词缀（反伤/减伤）"
                "以创造差异化。"
            ),
            tags=("block", "self_target"),
        ),
    ),
    # 手牌 / 防御端 / 成长性防御
    CardPrototype(
        card=BULWARK_PROTOTYPE,
        meta=CardPrototypeMeta(
            prototype_id="proto.bulwark",
            domain="手牌",
            port="防御端",
            port_subtype="成长性防御",
            name="防御蓄力",
            summary="格挡 + 保留，跨回合常驻防御。",
            guide=(
                "字段：block=3、retain=True、self_target=True。持有即计入总防御，"
                "retain 跨回合存续（占用下回合手牌名额）。"
            ),
            tags=("block", "retain"),
        ),
    ),
    CardPrototype(
        card=PASSIVE_PROTOTYPE,
        meta=CardPrototypeMeta(
            prototype_id="proto.passive",
            domain="手牌",
            port="防御端",
            port_subtype="成长性防御",
            name="常驻被动",
            summary="不可出 + 保留，每回合末结算持续状态。",
            guide=(
                "字段：playable=False、retain=True、on_turn_end_affixes=[常驻]。"
                "不可出但持有，收益（或减益）在每次 pass turn 结算。"
            ),
            tags=("playable", "retain", "on_turn_end_affixes"),
        ),
    ),
    # 手牌 / 防御端 / 特殊防御机制
    CardPrototype(
        card=THORNS_PROTOTYPE,
        meta=CardPrototypeMeta(
            prototype_id="proto.thorns",
            domain="手牌",
            port="防御端",
            port_subtype="特殊防御机制",
            name="反伤壁垒",
            summary="格挡 + 反伤，被打反制。",
            guide=(
                "字段：block=2、retain=True、on_hit_affixes=[反伤]。持有高防，"
                "被命中时反制攻击者。"
            ),
            tags=("block", "retain", "on_hit_affixes"),
        ),
    ),
    CardPrototype(
        card=SUPPORT_PROTOTYPE,
        meta=CardPrototypeMeta(
            prototype_id="proto.support",
            domain="手牌",
            port="防御端",
            port_subtype="特殊防御机制",
            name="支援分发",
            summary="转嫁增益给友方。",
            guide=(
                "字段：transferable=True、on_turn_end_affixes=[增益]。"
                "目标由 target_type 决定，传友分发增益（状态保护/支援）。"
            ),
            tags=("transferable", "on_turn_end_affixes"),
        ),
    ),
    CardPrototype(
        card=AOE_BUFF_PROTOTYPE,
        meta=CardPrototypeMeta(
            prototype_id="proto.aoe_buff",
            domain="手牌",
            port="防御端",
            port_subtype="特殊防御机制",
            name="群体增益",
            summary="ALL + 己方锚点，群体增益。",
            guide=(
                "字段：ALL + 己方锚点 + 增益词缀。作用于己方阵营全体（状态保护/支援）。"
            ),
            tags=("all", "on_turn_end_affixes"),
        ),
    ),
    # 装备
    CardPrototype(
        card=GEAR_OFFENSE_PROTOTYPE,
        meta=CardPrototypeMeta(
            prototype_id="gear.offense",
            domain="装备",
            port="攻击端",
            port_subtype="前端伤害",
            name="进攻装备",
            summary="出牌即时造成伤害，词缀集中在 on_play_affixes。",
            guide=(
                "字段：target_type=SINGLE、self_target=False、damage=3、hit_count=1、"
                "block=0、cost=1。即时词缀承载出牌伤害，伤害随填充叠加角色攻击力。"
                "润色：把即时词缀替换为具体效果，name/description 由系统沿用装备的。"
            ),
            tags=("on_play_affixes", "damage"),
        ),
    ),
    CardPrototype(
        card=GEAR_DEFENSE_PROTOTYPE,
        meta=CardPrototypeMeta(
            prototype_id="gear.defense",
            domain="装备",
            port="防御端",
            port_subtype="成长性防御",
            name="防御装备",
            summary="持有期提供格挡，受击时触发词缀，跨回合保留。",
            guide=(
                "字段：self_target=False、damage=0、block=3、cost=1、retain=True。"
                "持有期提供格挡（计入总防御），受击词缀触发反制，retain 跨回合保留。"
                "润色：把受击词缀替换为具体反制效果，name/description 由系统沿用装备的。"
            ),
            tags=("on_hit_affixes", "block", "retain"),
        ),
    ),
    CardPrototype(
        card=GEAR_CONTAGION_PROTOTYPE,
        meta=CardPrototypeMeta(
            prototype_id="gear.contagion",
            domain="装备",
            port="攻击端",
            port_subtype="成长性伤害",
            name="投掷/传染装备",
            summary="出牌后转移给敌人，回合结束对非 source 者持续结算。",
            guide=(
                "字段：transferable=True、retain=True、damage=1、hit_count=1、"
                "block=0、target_type=SINGLE。出牌后转移到目标手牌，回合结束词缀对非 source 者"
                "持续结算。润色：把回合结束词缀替换为具体持续效果，name/description 由系统沿用装备的。"
            ),
            tags=("transferable", "on_turn_end_affixes", "retain"),
        ),
    ),
]
