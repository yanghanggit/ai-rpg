from ..models import (
    ActorType,
    Actor,
    RPGCharacterProfile,
)
from .demo_utils import (
    CAMPAIGN_SETTING,
    create_actor,
)


def create_actor_goblin() -> Actor:
    """
    创建一个哥布林角色实例

    Returns:
        ActorType: 哥布林角色实例
    """
    return create_actor(
        name="角色.怪物.哥布林-拉格",
        character_sheet_name="goblin",
        kick_off_message="",
        rpg_character_profile=RPGCharacterProfile(base_dexterity=1),
        type=ActorType.MONSTER,
        campaign_setting=CAMPAIGN_SETTING,
        actor_profile="你是哥布林部落中狡黠而略有头脑的成员。与多数哥布林不同，你会主动与其他种族进行小规模交易，偶尔利用自己的狡诈为换取食物或装备做一些情报交换。这让你在部落内部既受嫉妒又被依赖。你心中对更强大的怪物势力既畏惧又渴望效忠，因此常常成为阴谋势力的耳目或先锋。",
        appearance="""身材比普通哥布林略微高挑，瘦削却敏捷。皮肤呈暗绿色，眼睛闪着黄褐色的光，透出无时无刻的警惕。鼻子小而上翘，双耳显得尖长。破旧的皮质护肩上挂着几颗用来炫耀战绩的兽牙，腰间除了短刃还挂着一个小皮囊，内里装着经常使用的毒粉或烟雾弹。""",
    )
