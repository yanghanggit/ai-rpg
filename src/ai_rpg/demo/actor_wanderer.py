from ..models import (
    Actor,
    Keyword,
    CharacterSheet,
    ActorType,
    CharacterStats,
)
from .global_settings import (
    RPG_CAMPAIGN_SETTING,
)
from .entity_factory import (
    create_actor,
)
from .rpg_system_rules import (
    RPG_SYSTEM_RULES,
)


def create_wanderer() -> Actor:
    """
    创建失忆旅行者角色实例（无名氏）。

    醒来时已身处沙漠遗迹，对自身来历毫无记忆，连名字也不存在。

    Returns:
        Actor: 无名氏角色实例
    """
    actor = create_actor(
        name="角色.旅行者.无名氏",
        character_sheet=CharacterSheet(
            name="wanderer",
            type=ActorType.ALLY,
            profile="""**历史**: 你没有历史。你醒来时仰躺在一片石板地面上，头顶是刺眼的日光与几根错位的断柱。手边什么都没有，脑海里也什么都没有——没有来处，没有去处，连名字也没有。你不知道自己是谁，也不知道为什么会出现在这里。"无名氏"不是名字，只是你暂时没有更好的东西可以用。
**性格**: 你沉默，观察多于开口。面对陌生的事物不会慌乱，而是停下来，仔细看，仔细想，再决定怎么做。你不排斥危险，但也不会轻易莽撞。
**禁忌**: 你对任何人强行拿走你身上仅有的东西、或强迫你去某个地方有本能的抵触。
**最爱**: 你发现自己喜欢在天刚亮、气温尚未攀升时独自在遗迹里走动，那时候周围很安静。""",
            base_body="年近三十的男性，仅着简单内衣。身形清瘦但不单薄，肩頸窄甄，胸领小，腰鈃紧进，没有明显的肌肉块感却也不浮肿，是长期行路的人才有的体型。肤色偏浅，颈臂交界处露出初晒的淡红痕迹，胸海和小腹胤色较浅。双腿细长而有力，小腿肌肉线条明显。手指细长，承接对点有轻茧。面容轮廓分明，眼神深沉，沉默时像在看某个他人看不见的地方。",
        ),
        character_stats=CharacterStats(),
        campaign_setting=RPG_CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
        keywords=[
            Keyword(
                description="多段连击型：每张卡牌优先生成多次攻击（hit_count ≥ 2），每段伤害较低但累积可观；格挡收益次要，damage_dealt 不为 0。"
            ),
            Keyword(
                description="状态控制型：每张卡牌的 effects 不得为空，优先生成能引发持续状态（如虚弱、减速、灼烧）的卡牌；damage_dealt 可以偏低甚至为 0，以控场效果为核心价値。"
            ),
        ],
    )

    return actor
