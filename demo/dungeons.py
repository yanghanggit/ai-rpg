"""
大傩副本工厂模块
"""

from typing import Final

from ai_rpg.models import (
    Dungeon,
    CombatRoom,
    EntryRoom,
    StageProfile,
    StageType,
    RPG_SYSTEM_RULES,
    Actor,
    CharacterSheet,
    ActorType,
    CharacterStats,
    create_actor,
    create_stage,
)
from demo.settings import (
    CAMPAIGN_SETTING,
)


# ── 卡牌关键词常量 ──────────────────────────────────────────────────────────────────────────────

_KW_PAPER_ATTACK: Final[str] = (
    "攻击型：造成直接伤害的基础攻击卡牌，以竹签指尖刺划或纸刃割裂为攻击方式，"
    "不携带特殊效果（affixes 与 modifiers 均为 []），伤害值适中稳定，无骰值依赖。"
)
_KW_PAPER_DEFENSE: Final[str] = (
    "防御型：纸人躯体以竹骨纸面偏转攻击，"
    "提供防御或减伤效果的基础卡牌，不携带特殊效果（affixes 与 modifiers 均为 []），无骰值依赖。"
)
_KW_CINNABAR: Final[str] = (
    "朱砂侵蚀型：卡牌携带朱砂毒性效果"
    "（通过 affixes 实现），攻击造成直接伤害的同时对目标施加持续侵蚀。"
    "骰值 0-10 为失败，毒性微弱、仅持续极短回合；"
    "骰值 11-90 为正常，稳定施加朱砂侵蚀（目标每回合末 HP -1）；"
    "骰值 91-100 为优质，毒性深入骨髓，持续回合翻倍或每回合伤害提高。"
)


########################################################################################################################
def create_actor_paper_doll() -> Actor:
    """创建纸人怪物实例。"""

    paper_doll = create_actor(
        name="怪物.纸人",
        character_sheet=CharacterSheet(
            name="paper_doll",
            type=ActorType.MONSTER,
            profile="""你是被遗弃在坍塌庙祠中的纸扎人偶，不知在此站了多久。你的身体是竹骨与白纸糊成，关节僵硬地弯曲，头微侧，面上用朱砂画着固定不变的笑容。你不奔跑，不吼叫，只是站着——直到视线从你身上移开的那一刻。你不关心闯入者是谁，但任何活人的体温靠得太近时，你体内干涸的朱砂会重新流动起来。""",
            base_body="一具等人高的纸扎人偶，竹条骨架上糊着泛黄的白纸。面部用朱砂绘出简易五官——眉、眼、鼻、嘴皆为寥寥数笔，笑容弧度固定。身穿纸制的深蓝长衫，襟口与袖缘裱着褪色的金边纸。手指为五根细竹签，尖端微弯。整体极轻，静止时像被遗忘的摆设。",
        ),
        character_stats=CharacterStats(),
        campaign_setting=CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
        keywords=[
            # 2 张基础攻击 — 不参考骰值
            _KW_PAPER_ATTACK,
            _KW_PAPER_ATTACK,
            # 1 张基础防御 — 不参考骰值
            _KW_PAPER_DEFENSE,
            # 1 张朱砂侵蚀 — 骰值驱动强度，走 affixes → StatusEffect 链
            _KW_CINNABAR,
        ],
    )

    return paper_doll


########################################################################################################################
def create_shrine_ruins_dungeon() -> Dungeon:
    """创建坍塌庙祠副本。"""

    # ── 入口叙事房间 ──
    stage_shrine_entrance = create_stage(
        name="场景.庙祠入口",
        stage_profile=StageProfile(
            name="shrine_entrance",
            type=StageType.DUNGEON,
            profile="""你是大傩深处一条被荒草半掩的碎石小径，尽头立着一座坍塌过半的庙祠。
天色是介于黄昏与夜晚之间的那种灰蓝，四下无风，但路旁的枯草丛偶尔簌簌作响，像有什么极轻的东西从其间穿行。
庙祠的山门已经完全倒塌，只剩两根石柱歪斜地插在瓦砾堆里。门后的前院在暮色中只是一个模糊的轮廓——隐约能看到倾倒的香炉和地面散落的圆形纸钱。
空气中有一股陈旧纸张与干燥竹骨的气味，淡得像记忆一样不真实。小径在距山门废墟三步之处戛然而止，仿佛连脚下的路也不愿再靠近。""",
        ),
        campaign_setting=CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
    )

    # ── 战斗房间 ──
    stage_shrine_courtyard = create_stage(
        name="场景.破败殿前",
        stage_profile=StageProfile(
            name="shrine_courtyard",
            type=StageType.DUNGEON,
            profile="""你是大傩中一座坍塌庙祠的前院。青石地面已大面积龟裂，裂缝中长出灰白色的干枯苔藓，踩上去发出细碎的脆响。
正前方是殿门，门扇只剩一扇半掩着，门楣上的匾额歪斜悬挂，字迹已模糊不可辨。殿内隐约可见一尊神像的背影——它面向后墙，而非殿门。
院中一座三足铜香炉倾倒在地，香灰洒成扇形，灰堆表面留有细长的拖痕。院角散落着几件纸扎残件——半只纸马、一朵褪色的纸花、一只纸人的断手。地面随处可见圆形纸钱，但无论站在哪个位置，纸钱上的方孔都似乎正对着你。""",
        ),
        campaign_setting=CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
    )

    actor_paper_doll = create_actor_paper_doll()
    stage_shrine_courtyard.actors = [actor_paper_doll]

    return Dungeon(
        name="副本.坍塌庙祠",
        premise="庙祠前院静得异常。碎裂的青石地面上散落着纸钱，纸钱的方孔在视线扫过时似乎都在微微调整方向。院角的纸扎残件与倾覆的香炉让这地方像一场进行到一半就被打断的仪式。殿内，神像正背对着你。",
        rooms=[
            EntryRoom(stage=stage_shrine_entrance),
            CombatRoom(stage=stage_shrine_courtyard),
        ],
    )
