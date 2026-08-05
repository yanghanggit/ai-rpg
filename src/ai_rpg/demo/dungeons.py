"""
大傩副本工厂模块
"""

from ..models import (
    Dungeon,
    CombatRoom,
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
from .settings import (
    CAMPAIGN_SETTING,
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
            "纯攻击型：每张卡牌专注于对单个敌人造成直接伤害，不携带任何附加效果或持续状态。骰值 0-30 为失败，攻击乏力、伤害偏低；骰值 31-70 为正常，伤害稳定适中；骰值 71-100 为优质，体现爆发感，伤害显著高于角色基础攻击力。"
        ],
    )

    return paper_doll


########################################################################################################################
def create_shrine_ruins_dungeon() -> Dungeon:
    """创建坍塌庙祠副本。"""

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
            CombatRoom(stage=stage_shrine_courtyard),
        ],
    )
