"""
常用技能定义模块

本模块定义了角色常用的技能常量，供各个角色创建函数使用。
使用 .model_copy() 方法复制技能实例以确保每个角色拥有独立的技能对象。
"""

from typing import Final
from ..models import Skill


WEAPON_ATTACK_SKILL: Final[Skill] = Skill(
    name="使用武器攻击",
    description="使用手中的武器或可触及的装备进行攻击行动，如刺击、斩击、砸击、投掷等。攻击方式和目标由实际场景决定。代价：全力攻击会降低防御。限制：如果没有武器或装备，此技能不会起任何作用，但仍需承受防御降低的惩罚代价。",
)

WEAPON_DEFEND_SKILL: Final[Skill] = Skill(
    name="使用武器防守",
    description="使用手中的武器或装备进行防御行动，如格挡、架开、闪避时借助装备保持平衡等。防守方式由实际场景决定。代价：无。",
)

UNARMED_COMBAT_SKILL: Final[Skill] = Skill(
    name="肉搏",
    description="使用身体进行徒手战斗，包括拳击、踢击、擒拿、摔投等格斗技巧。攻击方式和目标由实际场景决定。特性：肉搏攻击会寻找目标防御的薄弱点，可以无视目标的防御措施直接对身体造成伤害。代价：徒手攻击敌人的坚硬部位或武器时可能会受伤。",
)

BEAST_ATTACK_SKILL: Final[Skill] = Skill(
    name="野性攻击",
    description="使用爪牙、利齿等身体武器进行本能攻击，包括撕咬、扑击、抓挠等野兽战斗方式。攻击方式和目标由实际场景决定。特性：凶猛的攻击会破坏目标的防御姿态，削弱其防御能力。代价：无。",
)

THROW_SKILL: Final[Skill] = Skill(
    name="投掷",
    description="快速拾起周围可触及的物体并向目标投掷。投掷物的伤害、效果和命中率取决于物体本身的特性、重量和距离。代价：投掷动作需要专注于瞄准和发力，期间无法进行防御，容易被敌方趁机攻击。",
)

PERCEPTION_SKILL: Final[Skill] = Skill(
    name="感知",
    description="感知目标体内的灵气波动规律，发现其薄弱之处，在目标身上标记弱点。效果：目标进入易伤状态，受到的所有攻击伤害翻倍，直到弱点状态被消除。代价：感知过程需要专注凝神，自身防御会暂时减弱。",
)

INTIMIDATION_SKILL: Final[Skill] = Skill(
    name="威压",
    description="释放作为大妖的强大气息，震慑周围生灵。效果：降低目标的防御能力，同时激发自身凶性，提升攻击力。代价：大范围释放威压会消耗大量体力。",
)
