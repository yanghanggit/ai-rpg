"""卡牌原型：类型定义、注册表与默认牌单。

`CardPrototypeMeta` / `CardPrototype` 定义「卡牌原型 = 骨架 `Card` + 教学元数据」的
schema；`CARD_PROTOTYPES` 是全部原型的注册表，供 setup_demo 灌库、flush_card_prototypes
快刷、运行时按 `card_type` / `archetype` 检索。

骨架 `Card` 的定义与分类说明见 `demo/card_skeletons.py`。
逐级披露：一级 `meta.name` / `meta.summary` / `meta.keywords`；二级 `skeleton` 全字段 + `meta.guide`。
"""

from dataclasses import dataclass
from typing import Final, List, Tuple

from ai_rpg.models import Card
from demo.card_skeletons import (
    AOE_BUFF_SKELETON,
    AOE_DEBUFF_SKELETON,
    AOE_SKELETON,
    ATTACK_SKELETON,
    BULWARK_SKELETON,
    BURST_SKELETON,
    CONSUMABLE_AOE_SKELETON,
    CONSUMABLE_SINGLE_SKELETON,
    CONSUMABLE_SPREAD_SKELETON,
    DEADLINE_SKELETON,
    DEFENSE_SKELETON,
    DOT_SKELETON,
    FINISHER_SKELETON,
    FLEETING_SKELETON,
    FOCUS_SKELETON,
    GEAR_CONTAGION_SKELETON,
    GEAR_DEFENSE_SKELETON,
    GEAR_OFFENSE_SKELETON,
    MARK_SKELETON,
    PASSIVE_SKELETON,
    PIERCE_SKELETON,
    PLATE_SKELETON,
    SACRIFICE_SKELETON,
    SELF_LOOP_SKELETON,
    SHIELD_TRANSFER_SKELETON,
    SPREAD_SKELETON,
    SUPPORT_SKELETON,
    THORNS_SKELETON,
    THROW_SKELETON,
)


@dataclass(frozen=True)
class CardPrototypeMeta:
    """卡牌原型的检索元数据。"""

    prototype_id: str  # 稳定检索键，工具据此定位原型
    card_type: str  # 应用场景：手牌 / 装备
    archetype: str  # 三端大类：攻击端 / 防御端 / 运转端
    archetype_subtype: str  # 三端小类（见模块 docstring）
    name: str  # 索引展示名（教学性文本）
    summary: str  # 一级披露：一句话摘要，供列表与检索
    guide: str  # 二级披露：完整字段语义与设计指导，供展开
    keywords: Tuple[str, ...] = ()  # 检索标签（关键字段名）


@dataclass(frozen=True)
class CardPrototype:
    """一个已注册的卡牌原型 = 骨架 Card + 检索元数据。"""

    skeleton: Card
    meta: CardPrototypeMeta


#######################################################################################################################################
CARD_PROTOTYPES: Final[List[CardPrototype]] = [
    # 手牌 / 攻击端 / 前端伤害
    CardPrototype(
        skeleton=ATTACK_SKELETON,
        meta=CardPrototypeMeta(
            prototype_id="proto.attack",
            card_type="手牌",
            archetype="攻击端",
            archetype_subtype="前端伤害",
            name="基础攻击",
            summary="单目标直接伤害，最低成本的输出基线。",
            guide=(
                "字段：target_type=SINGLE、self_target=False、damage=2、hit_count=1、"
                "block=0、cost=1。填充牌库时 damage 叠加角色攻击力；block 为 0，不承担防御。"
                "设计指引：作为输出卡原型，变体在其上叠加词缀（穿甲/多段）或流转标志"
                "（exhaust/ethereal）以创造差异化。"
            ),
            keywords=("damage", "single"),
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
            summary="高费高伤 + 消耗，整场只此一次。",
            guide=(
                "字段：cost=3、damage=6、exhaust=True、SINGLE。整场只结算一次，"
                "允许效果明显超模，制造「何时出手」的时机抉择。"
            ),
            keywords=("exhaust", "damage", "cost"),
        ),
    ),
    CardPrototype(
        skeleton=SACRIFICE_SKELETON,
        meta=CardPrototypeMeta(
            prototype_id="proto.sacrifice",
            card_type="手牌",
            archetype="攻击端",
            archetype_subtype="前端伤害",
            name="代价爆发",
            summary="高伤 + 自伤代价，一次性爆发（代价自定）。",
            guide=(
                "字段：damage=5、exhaust=True、on_play_affixes（引导）。"
                "用即时词缀（减益）支付代价换取超模输出，高风险高回报。这是一条「取数」引导——"
                "请选一个（或组合）内建数值写成你自己的代价规则（如对本卡 damage 自伤、削减自身 "
                "block、透支自身气血换更重一击等）。"
            ),
            keywords=("exhaust", "damage", "on_play_affixes"),
        ),
    ),
    CardPrototype(
        skeleton=FOCUS_SKELETON,
        meta=CardPrototypeMeta(
            prototype_id="proto.focus",
            card_type="手牌",
            archetype="攻击端",
            archetype_subtype="前端伤害",
            name="集火连击",
            summary="单体多段爆发。",
            guide=(
                "字段：SINGLE、hit_count=3、damage=2。多段各自独立结算，集火单个目标。"
            ),
            keywords=("hit_count", "damage", "single"),
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
            guide=(
                "字段：SPREAD、hit_count=4。段数在敌阵营内随机或保底分配，适合清场。"
            ),
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
            guide=(
                "字段：on_play_affixes、SINGLE。这是一条「取数」引导，不是成品规则——"
                "请在骨架之上选一个（或组合）内建数值，写成你自己的一条 on_play 词缀"
                "（格式 `[词缀名]:机械结算描述`）。可选数值：本卡 damage/hit_count；"
                "目标的总格挡/当前 HP/最大 HP；自身的 HP/总格挡。"
                "可选方向：无视目标格挡直伤、借目标格挡加重本次伤害、"
                "借目标当前 HP 加重伤害、借自身气血搏命等。"
            ),
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
            guide=(
                "字段：ethereal=True、damage=2、on_play_affixes（引导）。"
                "限时兑现压力，逼玩家当回合决定用或弃。即时词缀为「取数」引导——"
                "请选一个（或组合）内建数值写成你自己的爆发规则。"
            ),
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
            guide=(
                "字段：ethereal=True、exhaust=True。二者不互斥：ethereal 管「留手」、"
                "exhaust 管「打出后」，叠加即「用或弃都永久消失」，双重期限压力。"
            ),
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
            guide=(
                "字段：retain=True、exhaust=True。retain 跨回合蓄力等时机，exhaust 保证"
                "打出后永久离场；二者作用于「留手」与「打出」两个互斥情境，不冲突。"
            ),
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
            guide=("字段：ALL、damage=2。以目标为锚点，作用于其所在阵营全体。"),
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
            name="持续减益传染",
            summary="转嫁 + 回合末持续减益（数值方向自定）。",
            guide=(
                "字段：transferable=True、retain=True、on_turn_end_affixes（引导）。"
                "副本落在目标手牌，每回合末对非 source 者触发一条持续减益规则——请选一个（或组合）"
                "内建数值写成你自己的具体词缀（如借本卡 damage 持续灼烧、借目标气血加重等）。"
            ),
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
            guide=(
                "字段：transferable=True、exhaust=True、on_turn_end_affixes（引导）。"
                "本体打出后进 ExhaustPile；副本进目标手牌且继承 exhaust=True（目标日后打出"
                "副本同样消耗），实现一次性传染。回合末词缀为「取数」引导，请实例化为你自己的一条具体规则。"
            ),
            keywords=("transferable", "exhaust", "on_turn_end_affixes"),
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
            guide=(
                "字段：transferable=True、on_hit_affixes（引导）、damage=1。出牌后副本进入目标手牌并"
                "保留 source；目标被命中时触发一条由这张牌承载的易伤规则——请选一个（或组合）内建"
                "数值写成你自己的具体词缀。无需独立状态存储——「破绽」就是这张留在对方手上的牌。"
            ),
            keywords=("transferable", "on_hit_affixes"),
        ),
    ),
    CardPrototype(
        skeleton=SELF_LOOP_SKELETON,
        meta=CardPrototypeMeta(
            prototype_id="proto.selfloop",
            card_type="手牌",
            archetype="攻击端",
            archetype_subtype="铺垫性攻击支持",
            name="自我调息",
            summary="锁定自身 + 保留，每回合末续战恢复（数值方向自定）。",
            guide=(
                "字段：self_target=True、retain=True、block=1、on_turn_end_affixes（引导）。"
                "牌跨回合留在手牌，每次 pass turn 触发一条续战规则；请选一个（或组合）内建数值"
                "写成你自己的具体词缀。持续效果由这张牌本身承载。"
            ),
            keywords=("self_target", "retain", "on_turn_end_affixes"),
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
            guide=(
                "字段：ALL + 敌阵营锚点、damage=1、on_play_affixes（引导）。一轮对整队结算穿透 block "
                "的伤害，为后续输出做铺垫。请选一个（或组合）内建数值写成你自己的破防规则"
                "（如本次伤害无视目标 block、借目标 block 反向加伤等）。"
            ),
            keywords=("all", "on_play_affixes"),
        ),
    ),
    # 手牌 / 防御端 / 前端防御
    CardPrototype(
        skeleton=DEFENSE_SKELETON,
        meta=CardPrototypeMeta(
            prototype_id="proto.defense",
            card_type="手牌",
            archetype="防御端",
            archetype_subtype="前端防御",
            name="基础防御",
            summary="为自身提供格挡，持有期间提升防御。",
            guide=(
                "字段：self_target=True（忽略 target_type）、damage=0、block=1、cost=1、retain=False。"
                "填充牌库时 block 叠加角色防御力；持有期间计入持有者总防御，与是否打出无关。"
                "基础防御强制 retain=False：未打出即进弃牌堆、随洗牌回到牌库循环，抓到手占用一个"
                "手牌位。retain 与防御是强力搭配，只留给成长性/特殊防御，基础型不得叠加 retain；"
                "差异化靠词缀（如受击词缀反伤/减伤）表达。"
            ),
            keywords=("block", "self_target"),
        ),
    ),
    # 手牌 / 防御端 / 成长性防御
    CardPrototype(
        skeleton=BULWARK_SKELETON,
        meta=CardPrototypeMeta(
            prototype_id="proto.bulwark",
            card_type="手牌",
            archetype="防御端",
            archetype_subtype="成长性防御",
            name="防御蓄力",
            summary="格挡 + 保留，跨回合常驻防御。",
            guide=(
                "字段：block=3、retain=True、self_target=True。持有即计入总防御，"
                "retain 跨回合存续（不占用下回合抓牌名额，是额外留在手牌的常驻格挡）。"
                "retain 与防御是强力搭配，应作为成长性防御少量出现，不得下放到基础防御。"
            ),
            keywords=("block", "retain"),
        ),
    ),
    CardPrototype(
        skeleton=PASSIVE_SKELETON,
        meta=CardPrototypeMeta(
            prototype_id="proto.passive",
            card_type="手牌",
            archetype="防御端",
            archetype_subtype="成长性防御",
            name="蛰伏",
            summary="不可出 + 保留，每回合末袭扰敌人（数值方向自定）。",
            guide=(
                "字段：playable=False、retain=True、damage=1、on_turn_end_affixes（引导）。"
                "不可出但持有，每次 pass turn 触发一条袭扰规则——请选一个（或组合）内建数值写成"
                "你自己的具体词缀；持续效果由这张牌本身承载。"
            ),
            keywords=("playable", "retain", "on_turn_end_affixes"),
        ),
    ),
    CardPrototype(
        skeleton=PLATE_SKELETON,
        meta=CardPrototypeMeta(
            prototype_id="proto.plate",
            card_type="手牌",
            archetype="防御端",
            archetype_subtype="成长性防御",
            name="常驻护甲",
            summary="不可出 + 格挡 + 保留，纯被动防御。",
            guide=(
                "字段：playable=False、block=3、retain=True。不可出但持有期计入总防御，"
                "retain 跨回合存续；playable=False 与 retain/block 组合即纯被动护甲。"
            ),
            keywords=("playable", "block", "retain"),
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
            guide=(
                "字段：block=2、retain=True、damage=2、on_hit_affixes（引导）。持有高防，"
                "被命中时触发一条针对出牌者的反制规则。这是一条「取数」引导而非成品——请选一个"
                "（或组合）内建数值写成你自己的一条具体词缀（如借出牌者气血反伤、借自身 block 反震、"
                "借本卡 damage 加重反刺等）。"
            ),
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
            guide=(
                "字段：transferable=True、block=1、on_turn_end_affixes（引导）。"
                "出牌后副本进入友方手牌，其持有者每次 pass turn 触发一条持续增益规则——请选一个"
                "（或组合）内建数值写成你自己的具体词缀（如按 block 回复、借自身气血等）。"
            ),
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
            guide=(
                "字段：transferable=True、block=3。副本携带确定性格挡进目标手牌，"
                "持有期计入目标总防御；与「支援分发」的区别在于用确定性 block 而非词缀承载支援。"
            ),
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
            guide=(
                "字段：ALL + 己方锚点、block=1、on_play_affixes（引导）。以友方为锚点展开己方阵营，"
                "打出时对全体触发一条群体增益规则——请选一个（或组合）内建数值写成你自己的具体词缀。"
            ),
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
            summary="结构示例：单体即时伤害装备（damage=3；无词缀，词缀自行设计）。",
            guide=(
                "结构：target_type=SINGLE、self_target=False、damage=3、hit_count=1、"
                "block=0、cost=1。只示范「出牌即打伤害」的骨架；示例刻意不带词缀——"
                "词缀的时机与内容由你依材料与词缀规范自行设计（不是本示例的字段）。"
                "速度被动示例：speed=+1（轻捷的进攻装备，先手更早）。"
            ),
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
            summary="结构示例：持有期格挡 + 跨回合保留（block=3、retain=True；无词缀）。",
            guide=(
                "结构：self_target=False、damage=0、block=3、cost=1、retain=True。"
                "示范「持有即加防、跨回合留下」的骨架；示例刻意不带词缀——"
                "词缀由你依规范自行设计。"
                "速度被动示例：speed=-1（厚重的防御装备，后手更晚）。"
            ),
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
            name="投掷/传染装备",
            summary="结构示例：出牌后转移给敌人并跨回合保留（transferable=True、retain=True；无词缀）。",
            guide=(
                "结构：transferable=True、retain=True、damage=1、hit_count=1、"
                "block=0、target_type=SINGLE。示范「出牌后落到对手手里」的骨架；"
                "示例刻意不带词缀——词缀由你依规范自行设计。"
                "速度被动示例：speed=0（中性，速度被动可与打法无关）。"
            ),
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
            summary="结构示例：0 费一次性的单体伤害消耗品（damage=4；无词缀，词缀自行设计）。",
            guide=(
                "结构：cost=0、exhaust=True、target_type=SINGLE、self_target=False、"
                "damage=4、hit_count=1、block=0。只示范「0 费即时打单体伤害」的骨架；"
                "示例刻意不带词缀——词缀的时机与内容由你依材料与词缀规范自行设计。"
            ),
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
            summary="结构示例：0 费一次性的阵营全体伤害消耗品（damage=2、target_type=ALL）。",
            guide=(
                "结构：cost=0、exhaust=True、target_type=ALL、self_target=False、"
                "damage=2、hit_count=1、block=0。示范「以单个敌人为锚点、结算全阵营敌人」"
                "的骨架；示例刻意不带词缀——词缀由你依规范自行设计。"
            ),
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
            summary="结构示例：0 费一次性的散射伤害消耗品（damage=2、hit_count=2、SPREAD）。",
            guide=(
                "结构：cost=0、exhaust=True、target_type=SPREAD、self_target=False、"
                "damage=2、hit_count=2、block=0。示范「多段随机分配到敌方阵营」的骨架；"
                "示例刻意不带词缀——词缀由你依规范自行设计。"
            ),
            keywords=("damage", "spread", "hit_count"),
        ),
    ),
]


# ── 默认牌单 ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DeckBuild:
    """一套默认牌库配置：按顺序引用原型 id，重复项表示副本份数。

    作为兜底牌库（assemble_deck_system.make_default_deck_cards）的数据来源，
    使运行时无需硬编码任何卡名与份数。
    """

    card_prototype_ids: Tuple[str, ...]


DEFAULT_DECK_BUILD: Final[DeckBuild] = DeckBuild(
    card_prototype_ids=(
        "proto.attack",
        "proto.attack",
        "proto.attack",
        "proto.defense",
        "proto.defense",
    )
)
