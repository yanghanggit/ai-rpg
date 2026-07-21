from ..models import (
    Actor,
    CharacterSheet,
    ActorType,
    CharacterStats,
    RPG_SYSTEM_RULES,
)
from .global_settings import (
    RPG_CAMPAIGN_SETTING,
)
from ..models.entity_factory import (
    create_actor,
)


def create_wanderer() -> Actor:
    """
    创建失忆旅行者角色实例（无名氏）。

    醒来时已身处沙漠遗迹，对自身来历毫无记忆，连名字也不存在。

    Returns:
        Actor: 无名氏角色实例
    """
    actor = create_actor(
        name="旅行者.无名氏",
        character_sheet=CharacterSheet(
            name="wanderer",
            type=ActorType.NPC,
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
            "即时破甲型：每张卡牌必须携带至少一个在出牌时立即生效的特殊效果，优先体现破甲、穿透、无视防御等特性；攻击必须造成直接伤害，特殊效果在本次结算中即时生效。骰值 0-30 为失败，破甲效果微弱、伤害偏低；骰值 31-70 为正常，效果稳定清晰；骰值 71-100 为优质，穿透效果犀利且伤害偏高。",
        ],
    )

    return actor
