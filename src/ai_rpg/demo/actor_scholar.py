from ..models import (
    Actor,
    Archetype,
    CharacterSheet,
    ActorType,
    CharacterStats,
)
from .global_settings import (
    RPG_CAMPAIGN_SETTING,
)
from .rpg_system_rules import (
    RPG_SYSTEM_RULES,
)
from .entity_factory import (
    create_actor,
)


def create_scholar() -> Actor:
    """
    创建失忆学者角色实例（维拉）。

    醒来时已身处沙漠遗迹，身旁有一本残破笔记，
    字迹是自己的，内容却完全无法回忆。

    Returns:
        Actor: 维拉角色实例
    """
    actor = create_actor(
        name="角色.学者.维拉",
        character_sheet=CharacterSheet(
            name="scholar_vera",
            type=ActorType.ALLY,
            profile="""**历史**: 你没有历史，或者说，你记不起来。你醒来时坐靠在遗迹的一根断柱边，膝盖上压着一本残破的笔记。翻开来全是密密麻麻的手写记录——字迹是你的，你认出了这一点，但那些内容对你来说像是陌生人写的东西。你隐约觉得自己曾经在研究某些东西，却无法回忆是什么，也不知道为什么会出现在这里。
**性格**: 你冷静，习惯用语言把观察到的东西整理清楚。比起沉默，你更倾向于开口，但说的往往是事实与推断，不是情绪。
**禁忌**: 你对毫无依据的臆断和盲目破坏未知事物有明确的反感，即使对方出于好意。
**最爱**: 把新发现的东西记进笔记；安静的时候拿出那本看不懂的旧记录，盯着上面的字迹发呆。""",
            base_body="二十五岁上下的女性，仅着简单内衣。骨架纤细，体态偏瘦，肩强笺小，锁骨稍显。胸领平坦，腰鈃细体但缺乏曲线感，双腿细长。肤色较浅，眼下有淡淡的暗沉，手腕内侧几条细血管隐隐可见。右手中指有长期握笔留下的淡色压痕。关节细小而明显，整体属于从事脑力劳动而非体力劳动的少年女性体型。",
        ),
        character_stats=CharacterStats(),
        campaign_setting=RPG_CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
        archetypes=[
            Archetype(
                description="状态控制型：每张卡牌的 affixes 不得为空，优先生成能引发持续状态（如虚弱、减速、灼烧）的卡牌；damage_dealt 可以偏低甚至为 0，以控场效果为核心价值。"
            )
        ],
    )

    return actor
