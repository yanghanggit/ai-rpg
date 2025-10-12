from ..models import (
    Actor,
    ActorType,
    RPGCharacterProfile,
)
from .campaign_setting import (
    FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
    FANTASY_WORLD_RPG_GLOBAL_GAME_MECHANICS,
)
from .utils import (
    create_actor,
)


def create_actor_goblin() -> Actor:
    """
    创建一个哥布林角色实例

    Returns:
        Actor: 哥布林角色实例
    """
    return create_actor(
        name="角色.怪物.哥布林-拉格",
        character_sheet_name="goblin",
        kick_off_message="",
        rpg_character_profile=RPGCharacterProfile(base_dexterity=1),
        type=ActorType.MONSTER.value,
        campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
        actor_profile="你是哥布林部落中狡黠而略有头脑的成员。与多数哥布林不同，你似乎天生就比其他哥布林聪明许多，懂得很多古老科技的使用方法，也经常做一些稀奇古怪的小玩意来改善部落里的生活。虽然部落里的很多老不死认为古代科技是危险的，不详的，但是你依然不为所动，想要通过科技改变命运",
        appearance="""身材比普通哥布林略微高挑，瘦削却敏捷。皮肤呈暗绿色，眼睛闪着黄褐色的光，透出无时无刻的警惕。鼻子小而上翘，双耳显得尖长。身上穿戴着许多从古代科技遗迹里找到的机械零件打造的装甲，破旧的背包里装着许多自己制造的小机器人，机器龙，机器狼等。腰间还挂着一把充满科技感的驽，似乎不需要弩箭也可以发射""",
        global_game_mechanics=FANTASY_WORLD_RPG_GLOBAL_GAME_MECHANICS,
    )
