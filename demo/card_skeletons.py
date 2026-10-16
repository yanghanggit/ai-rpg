"""卡牌原型骨架。

每个 `*_SKELETON` 是一张与游戏内容完全解耦的骨架 `Card`：机械字段（cost / damage /
hit_count / block / target_type / flags）是只读骨架，三类词缀是
「可设计槽位的引导」（非空＝可设计，规范见 `AFFIX_DESIGN_SPEC`），`name` / `description`
留空、由角色 agent 重写。

骨架与教学元数据在 `demo/card_prototypes.py` 组装成卡牌原型（`CardPrototype`）。
"""

from typing import Final

from ai_rpg.models import Card, TargetType

#######################################################################################################################################
# ── 基础骨架 ──────────────────────────────────────────────

ATTACK_SKELETON: Final[Card] = Card(
    name="基础攻击",
    description="",
    on_play_affixes=[],
    on_hit_affixes=[],
    on_turn_end_affixes=[],
    playable=True,
    exhaust=False,
    retain=False,
    ethereal=False,
    transferable=False,
    cost=1,
    damage=2,
    hit_count=1,
    block=0,
    target_type=TargetType.SINGLE,
)


DEFENSE_SKELETON: Final[Card] = Card(
    name="基础防御",
    description="",
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
    block=1,
    target_type=TargetType.SELF,
)


HEAL_SKELETON: Final[Card] = Card(
    name="即时治疗",
    description="",
    on_play_affixes=[
        "[词缀名]:打出时取一个内建数值为自身回复 HP（治疗方向；候选取数——本卡 block、自身 HP/最大 HP）"
    ],
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
    target_type=TargetType.SELF,
)


REGEN_SKELETON: Final[Card] = Card(
    name="持续调息",
    description="",
    on_play_affixes=[],
    on_hit_affixes=[],
    on_turn_end_affixes=[
        "[词缀名]:回合结束时取一个内建数值为本卡持有者回复 HP（持续恢复方向；候选取数——本卡 block、持有者 HP/最大 HP）"
    ],
    playable=False,
    exhaust=False,
    retain=True,
    ethereal=False,
    transferable=False,
    cost=1,
    damage=0,
    hit_count=1,
    block=1,
    target_type=TargetType.SELF,
)


# ── 攻击端骨架 ──────────────────────────────────────────────

BURST_SKELETON: Final[Card] = Card(
    name="一次性爆发",
    description="",
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
)


SACRIFICE_SKELETON: Final[Card] = Card(
    name="代价爆发",
    description="",
    on_play_affixes=[
        "[词缀名]:打出时取一个内建数值对自身结算代价（自损方向；候选取数——本卡 damage/block/hit_count、自身 HP/总格挡）"
    ],
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
)


FOCUS_SKELETON: Final[Card] = Card(
    name="集火连击",
    description="",
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
)


SPREAD_SKELETON: Final[Card] = Card(
    name="散射清场",
    description="",
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
)


MARK_SKELETON: Final[Card] = Card(
    name="转嫁破绽",
    description="",
    on_play_affixes=[],
    on_hit_affixes=[
        "[词缀名]:本卡持有者被命中时取一个内建数值对自身结算（易伤方向；候选取数——本卡 damage、自身总格挡/HP、出牌者 damage/hit_count）"
    ],
    on_turn_end_affixes=[],
    playable=True,
    exhaust=False,
    retain=False,
    ethereal=False,
    transferable=True,
    cost=1,
    damage=1,
    hit_count=1,
    block=0,
    target_type=TargetType.SINGLE,
)


PIERCE_SKELETON: Final[Card] = Card(
    name="借势攻击",
    description="",
    # 引导而非成品：以 `[词缀名]` 显形（模型化正确格式），但占位名会被校验拒（照抄必败）。
    on_play_affixes=[
        "[词缀名]:打出时取一个内建数值为变量对目标结算伤害（候选数值——本卡 damage/hit_count、目标的总格挡/当前 HP/最大 HP、自身的 HP/总格挡）。请把这条引导写成属于你的一条具体词缀。"
    ],
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
)


SELF_LOOP_SKELETON: Final[Card] = Card(
    name="自我调息",
    description="",
    on_play_affixes=[],
    on_hit_affixes=[],
    on_turn_end_affixes=[
        "[词缀名]:回合结束时取一个内建数值为自身结算（续战恢复方向；候选取数——本卡 block、自身 HP/最大 HP）"
    ],
    playable=True,
    exhaust=False,
    retain=True,
    ethereal=False,
    transferable=False,
    cost=1,
    damage=0,
    hit_count=1,
    block=1,
    target_type=TargetType.SELF,
)


FLEETING_SKELETON: Final[Card] = Card(
    name="限时机会",
    description="",
    on_play_affixes=[
        "[词缀名]:打出时取一个内建数值对目标额外结算（爆发方向；候选取数——本卡 damage/hit_count/block、目标总格挡/HP、自身 HP/总格挡）"
    ],
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
)


DEADLINE_SKELETON: Final[Card] = Card(
    name="限时终结",
    description="",
    on_play_affixes=[],
    on_hit_affixes=[],
    on_turn_end_affixes=[],
    playable=True,
    exhaust=True,
    retain=False,
    ethereal=True,
    transferable=False,
    cost=2,
    damage=4,
    hit_count=1,
    block=0,
    target_type=TargetType.SINGLE,
)


FINISHER_SKELETON: Final[Card] = Card(
    name="蓄力终结",
    description="",
    on_play_affixes=[],
    on_hit_affixes=[],
    on_turn_end_affixes=[],
    playable=True,
    exhaust=True,
    retain=True,
    ethereal=False,
    transferable=False,
    cost=3,
    damage=6,
    hit_count=1,
    block=0,
    target_type=TargetType.SINGLE,
)


DOT_SKELETON: Final[Card] = Card(
    name="持续减益转嫁",
    description="",
    on_play_affixes=[],
    on_hit_affixes=[],
    on_turn_end_affixes=[
        "[词缀名]:回合结束时取一个内建数值对非 source 者结算（持续减益方向；候选取数——本卡 damage、目标 HP/总格挡、自身 HP/总格挡）"
    ],
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
)


THROW_SKELETON: Final[Card] = Card(
    name="一次性投掷",
    description="",
    on_play_affixes=[],
    on_hit_affixes=[],
    on_turn_end_affixes=[
        "[词缀名]:回合结束时取一个内建数值对非 source 者结算（持续减益方向；候选取数——本卡 damage、目标 HP/总格挡、自身 HP/总格挡）"
    ],
    playable=True,
    exhaust=True,
    retain=False,
    ethereal=False,
    transferable=True,
    cost=1,
    damage=1,
    hit_count=1,
    block=0,
    target_type=TargetType.SINGLE,
)


AOE_SKELETON: Final[Card] = Card(
    name="群体打击",
    description="",
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
)


AOE_DEBUFF_SKELETON: Final[Card] = Card(
    name="群体穿甲",
    description="",
    on_play_affixes=[
        "[词缀名]:打出时取一个内建数值对目标阵营结算并绕过格挡（破防方向；候选取数——本卡 damage/hit_count、目标总格挡/HP）"
    ],
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
    target_type=TargetType.ALL,
)


# ── 防御端骨架 ──────────────────────────────────────────────

BULWARK_SKELETON: Final[Card] = Card(
    name="防御蓄力",
    description="",
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
    target_type=TargetType.SELF,
)


THORNS_SKELETON: Final[Card] = Card(
    name="反伤壁垒",
    description="",
    on_play_affixes=[],
    on_hit_affixes=[
        "[词缀名]:被命中时取一个内建数值反制出牌者（候选取数——出牌者 damage/HP/总格挡、本卡 damage/block、自身 HP/总格挡）"
    ],
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
    target_type=TargetType.SELF,
)


PASSIVE_SKELETON: Final[Card] = Card(
    name="蛰伏",
    description="",
    on_play_affixes=[],
    on_hit_affixes=[],
    on_turn_end_affixes=[
        "[词缀名]:回合结束时取一个内建数值为本卡持有者回复 HP（蛰伏回气方向；候选取数——本卡 damage/block、持有者 HP/最大 HP）"
    ],
    playable=False,
    exhaust=False,
    retain=True,
    ethereal=False,
    transferable=False,
    cost=1,
    damage=1,
    hit_count=1,
    block=0,
    target_type=TargetType.SELF,
)


PLATE_SKELETON: Final[Card] = Card(
    name="常驻护甲",
    description="",
    on_play_affixes=[],
    on_hit_affixes=[],
    on_turn_end_affixes=[],
    playable=False,
    exhaust=False,
    retain=True,
    ethereal=False,
    transferable=False,
    cost=1,
    damage=0,
    hit_count=1,
    block=3,
    target_type=TargetType.SELF,
)


SUPPORT_SKELETON: Final[Card] = Card(
    name="支援分发",
    description="",
    on_play_affixes=[],
    on_hit_affixes=[],
    on_turn_end_affixes=[
        "[词缀名]:回合结束时取一个内建数值为本卡持有者结算（持续增益方向；候选取数——本卡 block、自身 HP/最大 HP）"
    ],
    playable=True,
    exhaust=False,
    retain=False,
    ethereal=False,
    transferable=True,
    cost=1,
    damage=0,
    hit_count=1,
    block=1,
    target_type=TargetType.SINGLE,
)


SHIELD_TRANSFER_SKELETON: Final[Card] = Card(
    name="格挡支援",
    description="",
    on_play_affixes=[],
    on_hit_affixes=[],
    on_turn_end_affixes=[],
    playable=True,
    exhaust=False,
    retain=False,
    ethereal=False,
    transferable=True,
    cost=1,
    damage=0,
    hit_count=1,
    block=3,
    target_type=TargetType.SINGLE,
)


AOE_BUFF_SKELETON: Final[Card] = Card(
    name="群体鼓舞",
    description="",
    on_play_affixes=[
        "[词缀名]:打出时取一个内建数值为目标阵营全体结算（群体增益方向；候选取数——本卡 block、目标/自身 HP/总格挡）"
    ],
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
    block=1,
    target_type=TargetType.ALL,
)


# ── 自主运行骨架（召唤 / 图腾 / 光环等泛用；独留一个 summon 示例） ──────────

SUMMON_SKELETON: Final[Card] = Card(
    name="召唤.名字",
    description="",
    on_play_affixes=[],
    on_hit_affixes=[],
    on_turn_end_affixes=[],
    on_autonomous_affixes=[
        "[词缀名]:持有者每次 pass turn 的自主运行阶段，取一个内建数值对目标（敌人 / 友方，目标由你写明）自主结算一次（自主行动方向；候选取数——本卡 damage/hit_count/block、目标 HP/总格挡）"
    ],
    playable=False,
    exhaust=False,
    retain=True,
    ethereal=False,
    transferable=False,
    cost=1,
    damage=2,
    hit_count=1,
    block=0,
    target_type=TargetType.SINGLE,
)


# ── 装备骨架（工坊合成「选择核心 + 润色」用） ──────────────

GEAR_OFFENSE_SKELETON: Final[Card] = Card(
    name="装备.名字",
    description="",
    on_play_affixes=[],
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
)


GEAR_DEFENSE_SKELETON: Final[Card] = Card(
    name="装备.名字",
    description="",
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
)


GEAR_CONTAGION_SKELETON: Final[Card] = Card(
    name="装备.名字",
    description="",
    on_play_affixes=[],
    on_hit_affixes=[],
    on_turn_end_affixes=[],
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
)


# ── 消耗品骨架（工坊合成「选择核心 + 润色」用） ──────────────
#
# 消耗品卡固定 0 费（cost=0）且一次性（exhaust=True）：战斗中由 UseConsumableItemAction
# 物化进手牌后正常打出，用完进 ExhaustPile。本阶段只做伤害型（damage>0、block=0），
# 效果直接由 Card.damage 承载。

CONSUMABLE_SINGLE_SKELETON: Final[Card] = Card(
    name="消耗品.名字",
    description="",
    on_play_affixes=[],
    on_hit_affixes=[],
    on_turn_end_affixes=[],
    playable=True,
    exhaust=True,
    retain=False,
    ethereal=False,
    transferable=False,
    cost=0,
    damage=4,
    hit_count=1,
    block=0,
    target_type=TargetType.SINGLE,
)


CONSUMABLE_AOE_SKELETON: Final[Card] = Card(
    name="消耗品.名字",
    description="",
    on_play_affixes=[],
    on_hit_affixes=[],
    on_turn_end_affixes=[],
    playable=True,
    exhaust=True,
    retain=False,
    ethereal=False,
    transferable=False,
    cost=0,
    damage=2,
    hit_count=1,
    block=0,
    target_type=TargetType.ALL,
)


CONSUMABLE_SPREAD_SKELETON: Final[Card] = Card(
    name="消耗品.名字",
    description="",
    on_play_affixes=[],
    on_hit_affixes=[],
    on_turn_end_affixes=[],
    playable=True,
    exhaust=True,
    retain=False,
    ethereal=False,
    transferable=False,
    cost=0,
    damage=2,
    hit_count=2,
    block=0,
    target_type=TargetType.SPREAD,
)
