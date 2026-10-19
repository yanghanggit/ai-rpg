"""卡牌原型：类型定义、注册表与默认牌单。

`CardPrototypeMeta` / `CardPrototype` 定义「卡牌原型 = 骨架 `Card` + 教学元数据」的
schema；`CARD_PROTOTYPES` 是全部原型的注册表，供 setup_demo 灌库、flush_card_prototypes
快刷、运行时按 `card_type` / `archetype` 检索。

骨架 `Card` 的定义与分类说明见 `demo/card_skeletons.py`。
逐级披露：一级 `meta.name` / `meta.summary` / `meta.keywords`；二级 `skeleton` 全字段 + `meta.design`。

`meta.design` 是「这个原型用到什么就解释什么」的**原型专属设计说明**：
它自带本原型所涉字段/标志/词缀时机的语义与设计方向，不再依赖任何全局规范常量。
词缀的通用硬边界（结算原语、书写格式、取数、作用对象）由消费方提示词单独给出。
"""

from dataclasses import dataclass
from typing import Final, List, Tuple

from ai_rpg.models import Card
from demo.card_skeletons import (
    AOE_BUFF_SKELETON,
    AOE_DEBUFF_SKELETON,
    AOE_SKELETON,
    BASIC_ATTACK_SKELETON,
    BASIC_DEFENSE_SKELETON,
    BURST_SKELETON,
    CONSUMABLE_AOE_SKELETON,
    CONSUMABLE_SINGLE_SKELETON,
    CONSUMABLE_SPREAD_SKELETON,
    DEADLINE_SKELETON,
    DOT_SKELETON,
    FINISHER_SKELETON,
    FLEETING_SKELETON,
    GEAR_CONTAGION_SKELETON,
    GEAR_DEFENSE_SKELETON,
    GEAR_OFFENSE_SKELETON,
    HEAL_SKELETON,
    MARK_SKELETON,
    PIERCE_SKELETON,
    PLATE_SKELETON,
    REGEN_SKELETON,
    SHIELD_TRANSFER_SKELETON,
    SPREAD_SKELETON,
    SUMMON_SKELETON,
    SUPPORT_SKELETON,
    THORNS_SKELETON,
    THROW_SKELETON,
)


@dataclass(frozen=True)
class CardPrototypeMeta:
    """卡牌原型的检索元数据。"""

    prototype_id: str  # 稳定检索键，工具据此定位原型
    card_type: str  # 应用场景：手牌 / 装备 / 消耗品
    archetype: str  # 三端大类：攻击端 / 防御端 / 运转端
    archetype_subtype: str  # 三端小类（见模块 docstring）
    name: str  # 索引展示名（教学性文本）
    summary: str  # 一级披露：一句话摘要，供列表与检索
    design: str  # 二级披露：原型专属设计说明（用到什么就解释什么），供展开
    keywords: Tuple[str, ...] = ()  # 检索标签（关键字段名）
    tier: str = "normal"  # 层级：basic（开局必备、保底发放）/ normal（选型候选）


@dataclass(frozen=True)
class CardPrototype:
    """一个已注册的卡牌原型 = 骨架 Card + 检索元数据。"""

    skeleton: Card
    meta: CardPrototypeMeta


#######################################################################################################################################
# 开局必备基础牌：类似杀戮尖塔，每副初始牌组固定含这些「最基本」的牌；
# 它们是保底发放，不属于「选型」的成长/特殊牌；角色专属特殊牌另计（见 demo/world.py）。
BASIC_ATTACK_PROTOTYPE_ID: Final[str] = "proto.basic_attack"
BASIC_DEFENSE_PROTOTYPE_ID: Final[str] = "proto.basic_defense"
BASIC_ATTACK_COUNT: Final[int] = 3
BASIC_DEFENSE_COUNT: Final[int] = 2


#######################################################################################################################################
CARD_PROTOTYPES: Final[List[CardPrototype]] = [
    # 手牌 / 攻击端 / 前端伤害
    CardPrototype(
        skeleton=BASIC_ATTACK_SKELETON,
        meta=CardPrototypeMeta(
            prototype_id=BASIC_ATTACK_PROTOTYPE_ID,
            card_type="手牌",
            archetype="攻击端",
            archetype_subtype="前端伤害",
            name="基础攻击",
            summary="单目标直接伤害；数值与段数可调（单段基线 / 多段集火）。",
            design="""【骨架】target_type=SINGLE（单体，需指定 1 个目标）；cost=1、damage=2、hit_count=1、block=0。
【字段】damage 是单次伤害、hit_count 是攻击段数（>1 时每段独立结算）、block 是持有期格挡（计入持有者总防御）、cost 是出牌费用。
【设计】单体伤害基线。可微调 cost/damage/hit_count/block：低费单段＝输出基线，高费多段（hit_count>1）＝集火连击。本原型无词缀槽，只需设计 name/description。想要穿甲、词缀、流转差异，请改选带对应槽或标志的原型。""",
            keywords=("damage", "single"),
            tier="basic",
        ),
    ),
    CardPrototype(
        skeleton=BURST_SKELETON,
        meta=CardPrototypeMeta(
            prototype_id="proto.burst",
            card_type="手牌",
            archetype="攻击端",
            archetype_subtype="前端伤害",
            name="一次性爆发",
            summary="高费高伤 + 消耗，整场只此一次；可选一条自伤代价。",
            design="""【骨架】SINGLE；cost=3、damage=6、hit_count=1、block=0、exhaust=True；on_play_affixes 为可选引导槽。
【字段】exhaust：出牌后永久归入 ExhaustPile、不进弃牌循环，整场只此一次。on_play_affixes：本卡打出时结算，仅本次出牌生效；可留空。
【设计】高费高伤的时机抉择，允许效果明显超模。可微调 cost/damage/hit_count/block。若要做「代价爆发」，取一个（或组合）内建数值（本卡 damage/hit_count/block、自身 HP/总格挡）写一条代价词缀，方向必须对出牌者自身不利（如自伤 HP）；禁止写成对目标的额外收益或对自身的回复；也可以留空，只做纯爆发。词缀名要贴合角色/原型意象，不要直接复述机制名。""",
            keywords=("exhaust", "damage", "cost", "on_play_affixes"),
        ),
    ),
    CardPrototype(
        skeleton=SPREAD_SKELETON,
        meta=CardPrototypeMeta(
            prototype_id="proto.spread",
            card_type="手牌",
            archetype="攻击端",
            archetype_subtype="前端伤害",
            name="散射清场",
            summary="多段散射，不精确扩散。",
            design="""【骨架】target_type=SPREAD（散射：以目标为锚点散射其所在阵营）；cost=2、damage=1、hit_count=4、block=0。
【字段】SPREAD 的每一次命中独立随机落到阵营存活角色上：可重复命中同一人，也可能有人一次都没中（不做「每人至少一次」保底）。
【设计】多段随机扩散的清场原型。可微调 cost/damage/hit_count/block；无词缀槽，只需设计 name/description。""",
            keywords=("spread", "hit_count"),
        ),
    ),
    CardPrototype(
        skeleton=PIERCE_SKELETON,
        meta=CardPrototypeMeta(
            prototype_id="proto.pierce",
            card_type="手牌",
            archetype="攻击端",
            archetype_subtype="前端伤害",
            name="借势攻击",
            summary="攻击端·取数：借一个内建数值把这一击做重（无视格挡 / 借目标格挡 / 借目标气血）。",
            design="""【骨架】SINGLE；cost=1、damage=1、hit_count=1、block=0；on_play_affixes 为引导槽。
【字段】on_play_affixes：本卡打出时结算一次。
【设计】「借势」取数，不是成品：请在骨架上选一个（或组合）内建数值写成一条具体 on_play 词缀。可选变量：本卡 damage/hit_count；目标的总格挡/当前 HP/最大 HP；自身的 HP/总格挡。可选方向：无视目标格挡直伤、借目标格挡或当前 HP 加重本次伤害、借自身气血搏命等。词缀名要贴合角色/原型意象，不要直接复述机制名。""",
            keywords=("on_play_affixes", "damage", "single"),
        ),
    ),
    CardPrototype(
        skeleton=FLEETING_SKELETON,
        meta=CardPrototypeMeta(
            prototype_id="proto.fleeting",
            card_type="手牌",
            archetype="攻击端",
            archetype_subtype="前端伤害",
            name="限时机会",
            summary="虚无 + 高收益，不用即消失（爆发数值自定）。",
            design="""【骨架】SINGLE；cost=1、damage=2、hit_count=1、block=0、ethereal=True；on_play_affixes 为引导槽。
【字段】ethereal：pass turn 时若仍留在手牌则自动消耗（不用即消失）；on_play_affixes：本卡打出时结算一次。
【设计】限时兑现压力，逼玩家当回合决定用或弃。取一个（或组合）内建数值（本卡 damage/hit_count/block、目标 HP/总格挡、自身 HP/总格挡）写成一条额外伤害词缀。词缀名要贴合角色/原型意象，不要直接复述机制名。""",
            keywords=("ethereal", "on_play_affixes"),
        ),
    ),
    CardPrototype(
        skeleton=DEADLINE_SKELETON,
        meta=CardPrototypeMeta(
            prototype_id="proto.deadline",
            card_type="手牌",
            archetype="攻击端",
            archetype_subtype="前端伤害",
            name="限时终结",
            summary="虚无 + 消耗：用或弃都永久消失。",
            design="""【骨架】SINGLE；cost=2、damage=4、hit_count=1、exhaust=True、ethereal=True。
【字段】ethereal 管「留手」：pass turn 未出即消耗；exhaust 管「打出后」：永久离场。二者叠加＝用或弃都永久消失，作用于不同情境、不互斥。
【设计】双重期限压力。可微调 cost/damage/hit_count/block；无词缀槽，只需设计 name/description。""",
            keywords=("ethereal", "exhaust"),
        ),
    ),
    CardPrototype(
        skeleton=FINISHER_SKELETON,
        meta=CardPrototypeMeta(
            prototype_id="proto.finisher",
            card_type="手牌",
            archetype="攻击端",
            archetype_subtype="前端伤害",
            name="蓄力终结",
            summary="保留 + 消耗：跨回合蓄力，打出后永久离场。",
            design="""【骨架】SINGLE；cost=3、damage=6、hit_count=1、exhaust=True、retain=True。
【字段】retain：回合末保留在手牌、跨回合蓄力等时机；exhaust：打出后永久离场。二者作用于「留手」与「打出」两个不同情境，不冲突。
【设计】蓄力型终结技。可微调 cost/damage/hit_count/block；无词缀槽，只需设计 name/description。""",
            keywords=("retain", "exhaust"),
        ),
    ),
    CardPrototype(
        skeleton=AOE_SKELETON,
        meta=CardPrototypeMeta(
            prototype_id="proto.aoe",
            card_type="手牌",
            archetype="攻击端",
            archetype_subtype="前端伤害",
            name="群体打击",
            summary="ALL + 伤害，群体打击。",
            design="""【骨架】target_type=ALL（阵营锚点：以指定目标为锚点，作用于其所在阵营的全部存活角色）；cost=2、damage=2、hit_count=1、block=0。
【字段】ALL：对锚点阵营全体各结算一次。
【设计】群体打击。可微调 cost/damage/hit_count/block；无词缀槽，只需设计 name/description。""",
            keywords=("all", "damage"),
        ),
    ),
    # 手牌 / 攻击端 / 成长性伤害
    CardPrototype(
        skeleton=DOT_SKELETON,
        meta=CardPrototypeMeta(
            prototype_id="proto.dot",
            card_type="手牌",
            archetype="攻击端",
            archetype_subtype="成长性伤害",
            name="持续减益转嫁",
            summary="转嫁 + 回合末持续减益（数值方向自定）。",
            design="""【骨架】SINGLE；cost=1、damage=1、hit_count=1、block=0、transferable=True、retain=True；on_turn_end_affixes 为引导槽。
【字段】transferable：出牌时额外为每个解析目标手牌 copy 一份，副本落地即 transferable=False（只传一跳、不可再转手），本体照常结算；retain：回合末保留在手牌。on_turn_end_affixes：持有者每次 pass turn 结算一次，效果目标恒为持有者本人。
【设计】把持续减益投给敌人：副本落在目标手牌后，每回合末触发一条减益。请取一个（或组合）内建数值（本卡 damage、持有者 HP/总格挡等）写成一条词缀。方向必须让持有者（敌人）每回合受损；禁止回复或增益持有者。因带 transferable，可用「非 source 者」只伤外人、不反噬原主。词缀名要贴合角色/原型意象，不要直接复述机制名。""",
            keywords=("transferable", "retain", "on_turn_end_affixes"),
        ),
    ),
    CardPrototype(
        skeleton=THROW_SKELETON,
        meta=CardPrototypeMeta(
            prototype_id="proto.throw",
            card_type="手牌",
            archetype="攻击端",
            archetype_subtype="成长性伤害",
            name="一次性投掷",
            summary="出牌即消耗本体，副本进目标手牌持续受损（数值方向自定）。",
            design="""【骨架】SINGLE；cost=1、damage=1、hit_count=1、block=0、transferable=True、exhaust=True；on_turn_end_affixes 为引导槽。
【字段】transferable：出牌后副本进目标手牌、落地即 transferable=False（只投一次、不可再转手）；exhaust：本体打出后进 ExhaustPile，副本继承 exhaust=True（目标日后打出副本同样消耗）。on_turn_end_affixes：副本持有者每次 pass turn 结算一次，效果目标恒为持有者本人。
【设计】一次性投掷：本体消费、副本持续损人。取内建数值写成具体回合末词缀；可用「非 source 者」定向。词缀名要贴合角色/原型意象，不要直接复述机制名。""",
            keywords=("transferable", "exhaust", "on_turn_end_affixes"),
        ),
    ),
    # 手牌 / 攻击端 / 自主运行（独留一个 summon 示例；retain 可置 True）
    CardPrototype(
        skeleton=SUMMON_SKELETON,
        meta=CardPrototypeMeta(
            prototype_id="proto.summon",
            card_type="手牌",
            archetype="攻击端",
            archetype_subtype="自主运行",
            name="召唤兽",
            summary="抓到即召唤、retain 常驻；每回合自主运行一次，可攻击敌人或辅助我方。",
            design="""【骨架】SINGLE；cost=1、damage=2、hit_count=1、block=0、playable=False、retain=True；on_autonomous_affixes 为引导槽。
【字段】playable=False：不可出牌，进入手牌即视为召唤成功、作为持有状态；retain 使其跨回合常驻。on_autonomous_affixes：持有者每次 pass turn（在回合结束词缀之后）由所在场景结算一次；与回合结束词缀的根本区别是效果目标为场上任意存活角色（敌人/友方/持有者），由词缀文本写明目标如何选取；其造成的伤害算命中，会触发被命中者的受击词缀。
【设计】召唤兽 / 图腾 / 光环 / 持续诅咒：卡牌作为自主主体影响全场。取一个（或组合）内建数值写成具体自主词缀（如对一名随机敌人造成本卡 damage 的伤害）。该机制能力较强（近似「小神器」），宜克制。词缀名要贴合角色/原型意象，不要直接复述机制名。""",
            keywords=("on_autonomous_affixes", "retain", "autonomous"),
        ),
    ),
    # 手牌 / 攻击端 / 铺垫性攻击支持
    CardPrototype(
        skeleton=MARK_SKELETON,
        meta=CardPrototypeMeta(
            prototype_id="proto.mark",
            card_type="手牌",
            archetype="攻击端",
            archetype_subtype="铺垫性攻击支持",
            name="转嫁破绽",
            summary="把受击易伤投递给敌人，状态由这张牌本身承载（数值方向自定）。",
            design="""【骨架】SINGLE；cost=1、damage=1、hit_count=1、block=0、transferable=True；on_hit_affixes 为引导槽。
【字段】transferable：出牌后副本进入目标手牌并保留原 source，落地即 transferable=False（只传一跳、不可再转手）。on_hit_affixes：本卡持有者被命中时触发。
【设计】把「破绽」投给敌人：易伤规则由这张留在对方手上的牌承载，无需独立状态存储。取一个（或组合）内建数值（本卡 damage、出牌者 damage/hit_count、持有者 HP/总格挡）写成一条受击词缀。方向必须让持有者（敌人）更吃亏——多受伤害、失去 HP、削减其格挡等；禁止写成反伤、回复、增幅等对持有者有利的效果（那是反伤原型的方向）。词缀名要贴合角色/原型意象，不要直接复述机制名。""",
            keywords=("transferable", "on_hit_affixes"),
        ),
    ),
    CardPrototype(
        skeleton=AOE_DEBUFF_SKELETON,
        meta=CardPrototypeMeta(
            prototype_id="proto.aoe_debuff",
            card_type="手牌",
            archetype="攻击端",
            archetype_subtype="铺垫性攻击支持",
            name="群体穿甲",
            summary="ALL + 敌阵营，群体破防打击（破防方式自定）。",
            design="""【骨架】target_type=ALL + 敌阵营锚点；cost=1、damage=1、hit_count=1、block=0；on_play_affixes 为引导槽。
【字段】ALL：对锚点所在阵营全体结算。on_play_affixes：本卡打出时结算一次。
【设计】群体破防：一轮对整队结算可穿透格挡的伤害（格挡只读、不能写入）。请取内建数值写成具体破防词缀，如本次伤害无视目标 block、借目标 block 反向加伤等。词缀名要贴合角色/原型意象，不要直接复述机制名。""",
            keywords=("all", "on_play_affixes"),
        ),
    ),
    # 手牌 / 防御端 / 前端防御
    CardPrototype(
        skeleton=BASIC_DEFENSE_SKELETON,
        meta=CardPrototypeMeta(
            prototype_id=BASIC_DEFENSE_PROTOTYPE_ID,
            card_type="手牌",
            archetype="防御端",
            archetype_subtype="前端防御",
            name="基础防御",
            summary="为自身提供格挡，持有期间提升防御。",
            design="""【骨架】target_type=SELF；cost=1、damage=0、hit_count=1、block=1、retain=False、playable=False。
【字段】block：持有期计入持有者总防御；playable=False：纯持有价值、不可出牌（打出只会失去格挡）。retain=False：回合末离开手牌、随洗牌回到牌库循环，抓到手占用一个手牌位。
【设计】基础防御基线，强制不叠加 retain——retain 与防御是强力搭配，只留给成长性/特殊防御，基础型不得使用。可微调 cost/block；无词缀槽，只需设计 name/description。差异化靠词缀（如受击反伤/减伤），请改选带词缀槽的原型。""",
            keywords=("block", "target_type"),
            tier="basic",
        ),
    ),
    # 手牌 / 防御端 / 成长性防御
    CardPrototype(
        skeleton=PLATE_SKELETON,
        meta=CardPrototypeMeta(
            prototype_id="proto.plate",
            card_type="手牌",
            archetype="防御端",
            archetype_subtype="成长性防御",
            name="常驻护甲",
            summary="不可出 + 格挡 + 保留，跨回合常驻防御。",
            design="""【骨架】target_type=SELF；cost=1、damage=0、hit_count=1、block=3、playable=False、retain=True。
【字段】playable=False + retain + block：不可出、跨回合持有、持有期即计入总防御，构成纯被动护甲；block 可调，控制常驻强度。
【设计】常驻格挡：不可出、跨回合持有、持有期计入总防御。可微调 cost/block；无词缀槽，只需设计 name/description。""",
            keywords=("playable", "block", "retain"),
        ),
    ),
    # 手牌 / 防御端 / 恢复
    CardPrototype(
        skeleton=HEAL_SKELETON,
        meta=CardPrototypeMeta(
            prototype_id="proto.heal",
            card_type="手牌",
            archetype="防御端",
            archetype_subtype="恢复",
            name="即时治疗",
            summary="打出即回复自身（数值方向自定）。",
            design="""【骨架】target_type=SELF；cost=1、damage=0、hit_count=1、block=0；on_play_affixes 为引导槽。
【字段】on_play_affixes：本卡打出时结算一次。
【设计】即时治疗：只写回复（HP），不要引入伤害或格挡。请取一个（或组合）内建数值写成具体词缀，如回复本卡 block、按自身已损失 HP 回复等。词缀名要贴合角色/原型意象，不要直接复述机制名。""",
            keywords=("on_play_affixes", "target_type"),
        ),
    ),
    CardPrototype(
        skeleton=REGEN_SKELETON,
        meta=CardPrototypeMeta(
            prototype_id="proto.regen",
            card_type="手牌",
            archetype="防御端",
            archetype_subtype="恢复",
            name="持续调息",
            summary="不可出 + 保留，每回合末回复自身（数值方向自定）。",
            design="""【骨架】target_type=SELF；cost=1、damage=0、hit_count=1、block=1、playable=False、retain=True；on_turn_end_affixes 为引导槽。
【字段】playable=False + retain：不可出但跨回合持有；block 持有期提供格挡（可调为 0，做纯回气）。on_turn_end_affixes：每次 pass turn 结算一次，效果目标恒为持有者本人。
【设计】持续回气：持有者每回合末回复。取一个（或组合）内建数值（本卡 damage/block、自身 HP/最大 HP）写成具体词缀，只写回复（HP）；禁止写格挡。持续效果由这张牌本身承载。词缀名要贴合角色/原型意象，不要直接复述机制名。""",
            keywords=("playable", "retain", "on_turn_end_affixes"),
        ),
    ),
    # 手牌 / 防御端 / 特殊防御机制
    CardPrototype(
        skeleton=THORNS_SKELETON,
        meta=CardPrototypeMeta(
            prototype_id="proto.thorns",
            card_type="手牌",
            archetype="防御端",
            archetype_subtype="特殊防御机制",
            name="反伤壁垒",
            summary="格挡 + 反制：被打时借一个数值还击（方向自定）。",
            design="""【骨架】target_type=SELF；cost=1、damage=2、hit_count=1、block=2、retain=True、playable=False；on_hit_affixes 为引导槽。
【字段】block=2：持有期防御；retain：跨回合持有；playable=False：纯持有反伤，不可出牌。on_hit_affixes：本卡持有者被命中时触发。
【设计】反伤壁垒：被命中时触发一条针对出牌者的反制。这是一条「取数」引导而非成品——请取一个（或组合）内建数值（出牌者 damage/HP/总格挡、本卡 damage/block、自身 HP/总格挡）写成一条反制词缀，只反制攻击者；禁止治疗或增益持有者自身。词缀名要贴合角色/原型意象，不要直接复述机制名。""",
            keywords=("block", "retain", "on_hit_affixes"),
        ),
    ),
    CardPrototype(
        skeleton=SUPPORT_SKELETON,
        meta=CardPrototypeMeta(
            prototype_id="proto.support",
            card_type="手牌",
            archetype="防御端",
            archetype_subtype="特殊防御机制",
            name="支援分发",
            summary="转嫁持续增益给友方（数值方向自定）。",
            design="""【骨架】SINGLE；cost=1、damage=0、hit_count=1、block=1、transferable=True；on_turn_end_affixes 为引导槽。
【字段】transferable：出牌后副本进入友方手牌、落地即 transferable=False（只传一跳、不可再转手）；block=1 持有期提供格挡。on_turn_end_affixes：副本持有者每次 pass turn 结算一次，效果目标恒为持有者本人。
【设计】支援分发：把持续增益投给友方。取一个（或组合）内建数值（本卡 block、持有者 HP/最大 HP）写成一条词缀，方向须对持有者（友方）有利（回复 HP 等）；禁止伤害持有者。词缀名要贴合角色/原型意象，不要直接复述机制名。""",
            keywords=("transferable", "on_turn_end_affixes"),
        ),
    ),
    CardPrototype(
        skeleton=SHIELD_TRANSFER_SKELETON,
        meta=CardPrototypeMeta(
            prototype_id="proto.shield_transfer",
            card_type="手牌",
            archetype="防御端",
            archetype_subtype="特殊防御机制",
            name="格挡支援",
            summary="出牌把确定性格挡副本分发给队友。",
            design="""【骨架】SINGLE；cost=1、damage=0、hit_count=1、block=3、transferable=True。
【字段】transferable：出牌后副本进入目标手牌、落地即 transferable=False（只传一跳、不可再转手），副本携带确定性的 block=3，持有期计入目标总防御。
【叠加】若同时改为 SPREAD（骨架不禁止，需自行判断是否值得），命中按纯随机分配、每次命中发一份副本：同一目标被命中 k 次即得 k 份，持有期 block 合计 k×3，且每份都要付 cost 才能打出——属高方差高代价组合，定价时按此对待。
【设计】格挡支援：用确定性 block 而非词缀承载支援，与「支援分发」的区别即在此。可微调 cost/block；无词缀槽，只需设计 name/description。""",
            keywords=("transferable", "block"),
        ),
    ),
    CardPrototype(
        skeleton=AOE_BUFF_SKELETON,
        meta=CardPrototypeMeta(
            prototype_id="proto.aoe_buff",
            card_type="手牌",
            archetype="防御端",
            archetype_subtype="特殊防御机制",
            name="群体鼓舞",
            summary="ALL + 己方锚点，群体即时增益（数值方向自定）。",
            design="""【骨架】target_type=ALL + 己方锚点；cost=1、damage=0、hit_count=1、block=1；on_play_affixes 为引导槽。
【字段】ALL：以友方为锚点展开己方阵营、对全体结算。on_play_affixes：本卡打出时结算一次。
【设计】群体鼓舞：打出时对全体触发一条增益。取一个（或组合）内建数值（本卡 block、目标/自身 HP/总格挡）写成具体词缀；注意格挡只读、不能写入。词缀名要贴合角色/原型意象，不要直接复述机制名。""",
            keywords=("all", "on_play_affixes"),
        ),
    ),
    # 装备
    CardPrototype(
        skeleton=GEAR_OFFENSE_SKELETON,
        meta=CardPrototypeMeta(
            prototype_id="gear.offense",
            card_type="装备",
            archetype="攻击端",
            archetype_subtype="前端伤害",
            name="进攻装备",
            summary="单体即时伤害装备（damage=3，on_play 词缀槽）。",
            design="""【骨架】target_type=SINGLE；cost=1、damage=3、hit_count=1、block=0；on_play_affixes 为引导槽。
【字段】on_play_affixes：本卡打出时结算一次。
【设计】进攻装备：可微调 cost/damage/hit_count/block；取内建数值（本卡 damage/hit_count、目标 HP/总格挡）写成一条 on_play 伤害词缀（可为空）。只做伤害，不要治疗/格挡/状态。词缀名要贴合角色/原型意象，不要直接复述机制名。""",
            keywords=("damage", "single"),
        ),
    ),
    CardPrototype(
        skeleton=GEAR_DEFENSE_SKELETON,
        meta=CardPrototypeMeta(
            prototype_id="gear.defense",
            card_type="装备",
            archetype="防御端",
            archetype_subtype="成长性防御",
            name="防御装备",
            summary="持有期格挡 + 跨回合保留（block=3、retain=True，on_hit 词缀槽）。",
            design="""【骨架】target_type=SINGLE；cost=1、damage=0、hit_count=1、block=3、retain=True、playable=False；on_hit_affixes 为引导槽。
【字段】retain：跨回合留在手牌；block=3 持有期提供格挡；playable=False：纯持有防御，不可出牌。on_hit_affixes：本卡持有者被命中时触发。
【设计】防御装备：可微调 cost/damage/hit_count/block；取内建数值（本卡 block、自身 HP/总格挡）写成一条 on_hit 反制/减伤词缀（可为空）。词缀名要贴合角色/原型意象，不要直接复述机制名。""",
            keywords=("block", "retain"),
        ),
    ),
    CardPrototype(
        skeleton=GEAR_CONTAGION_SKELETON,
        meta=CardPrototypeMeta(
            prototype_id="gear.contagion",
            card_type="装备",
            archetype="攻击端",
            archetype_subtype="成长性伤害",
            name="投掷/转嫁装备",
            summary="出牌后转移给敌人并跨回合保留（transferable=True、retain=True，on_turn_end 词缀槽）。",
            design="""【骨架】target_type=SINGLE；cost=1、damage=1、hit_count=1、block=0、transferable=True、retain=True；on_turn_end_affixes 为引导槽。
【字段】transferable：出牌后副本落到目标手牌，只传一跳（落地即 transferable=False、不可再转手）；retain：跨回合保留。on_turn_end_affixes：副本持有者每次 pass turn 结算一次，效果目标恒为持有者本人。
【设计】投掷/转嫁装备：可微调 cost/damage/hit_count/block；取内建数值（本卡 damage、持有者 HP/总格挡）写成一条 on_turn_end 持续减益词缀（可为空），方向须让持有者（敌人）受损。词缀名要贴合角色/原型意象，不要直接复述机制名。""",
            keywords=("transferable", "retain"),
        ),
    ),
    # 消耗品（0 费一次性伤害卡）
    CardPrototype(
        skeleton=CONSUMABLE_SINGLE_SKELETON,
        meta=CardPrototypeMeta(
            prototype_id="consumable.single",
            card_type="消耗品",
            archetype="攻击端",
            archetype_subtype="单体伤害",
            name="单体伤害消耗品",
            summary="0 费一次性的单体伤害消耗品（damage=4，on_play 词缀槽）。",
            design="""【骨架】target_type=SINGLE；cost=0、damage=4、hit_count=1、block=0、exhaust=True、playable=True；cost/block 固定不可改。
【字段】on_play_affixes：本卡打出时结算一次，是唯一的词缀槽。
【设计】0 费一次性的单体伤害消耗品。可微调 damage/hit_count；取内建数值（本卡 damage/hit_count、目标 HP/总格挡）写成一条 on_play 伤害词缀（可为空）。只做伤害，不要治疗/格挡/状态。词缀名要贴合角色/原型意象，不要直接复述机制名。""",
            keywords=("damage", "single"),
        ),
    ),
    CardPrototype(
        skeleton=CONSUMABLE_AOE_SKELETON,
        meta=CardPrototypeMeta(
            prototype_id="consumable.aoe",
            card_type="消耗品",
            archetype="攻击端",
            archetype_subtype="群体伤害",
            name="群体伤害消耗品",
            summary="0 费一次性的阵营全体伤害消耗品（damage=2、target_type=ALL，on_play 词缀槽）。",
            design="""【骨架】target_type=ALL；cost=0、damage=2、hit_count=1、block=0、exhaust=True、playable=True；cost/block 固定不可改。
【字段】ALL：以单个敌人为锚点、结算其所在阵营全体。on_play_affixes：本卡打出时结算一次，是唯一的词缀槽。
【设计】0 费一次性的阵营全体伤害消耗品。可微调 damage/hit_count；取内建数值写成一条 on_play 伤害词缀（可为空）。只做伤害，不要治疗/格挡/状态。词缀名要贴合角色/原型意象，不要直接复述机制名。""",
            keywords=("damage", "all"),
        ),
    ),
    CardPrototype(
        skeleton=CONSUMABLE_SPREAD_SKELETON,
        meta=CardPrototypeMeta(
            prototype_id="consumable.spread",
            card_type="消耗品",
            archetype="攻击端",
            archetype_subtype="散射伤害",
            name="散射伤害消耗品",
            summary="0 费一次性的散射伤害消耗品（damage=2、hit_count=2、SPREAD，on_play 词缀槽）。",
            design="""【骨架】target_type=SPREAD；cost=0、damage=2、hit_count=2、block=0、exhaust=True、playable=True；cost/block 固定不可改。
【字段】SPREAD：以目标为锚点散射其所在阵营，多段随机分配。on_play_affixes：本卡打出时结算一次，是唯一的词缀槽。
【设计】0 费一次性的散射伤害消耗品。可微调 damage/hit_count；取内建数值写成一条 on_play 伤害词缀（可为空）。只做伤害，不要治疗/格挡/状态。词缀名要贴合角色/原型意象，不要直接复述机制名。""",
            keywords=("damage", "spread", "hit_count"),
        ),
    ),
]


# ── 默认牌单 ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DeckBuild:
    """一套默认牌库配置：按顺序引用原型 id，重复项表示副本份数。

    作为兜底牌库（assemble_dungeon_deck_system.make_default_deck_cards）的数据来源，
    使运行时无需硬编码任何卡名与份数。
    """

    card_prototype_ids: Tuple[str, ...]


# 兜底/保底牌单：全部由 basic 层原型构成（基础攻击 × N + 基础防御 × M）。
# 角色的实际开局牌组＝这份基础牌单的量 + 1 张角色专属特殊牌（见 demo/world.py）。
DEFAULT_DECK_BUILD: Final[DeckBuild] = DeckBuild(
    card_prototype_ids=(
        (BASIC_ATTACK_PROTOTYPE_ID,) * BASIC_ATTACK_COUNT
        + (BASIC_DEFENSE_PROTOTYPE_ID,) * BASIC_DEFENSE_COUNT
    )
)
