from ..models import (
    Actor,
    ActorType,
    RPGCharacterProfile,
)
from .campaign_setting import FANTASY_WORLD_RPG_CAMPAIGN_SETTING
from .utils import (
    create_actor,
)


def create_actor_wizard() -> Actor:
    """
    创建一个法师角色实例

    Returns:
        Actor: 法师角色实例
    """
    return create_actor(
        name="角色.法师.奥露娜",
        character_sheet_name="wizard",
        kick_off_message=f"""你已苏醒，准备开始冒险。告诉我你是谁？（请说出你的全名。）并告诉我你的战斗角色职能。回答简短(<100字)。""",
        rpg_character_profile=RPGCharacterProfile(base_max_hp=1000),
        type=ActorType.HERO,
        campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
        actor_profile="你是精灵王国天赋卓绝却格格不入的精灵法师，痴迷于召唤魔法，经常召唤出别的位面的古怪生物，这让你在故乡被视为“古怪”。作为法师，你的体力和力量也相应的很小，所以对于要用体力和力量进行的行动不感兴趣。对古老奥秘的渴求驱使你独自游历艾尔法尼亚。你极度反感滥用或扭曲魔法的行为，虽精通精灵传统却更热衷研究异族技艺与失落典籍。你啜饮月光露水调和的草药茶，却意外钟情人类蜂蜜蛋糕。你的终极目标是寻找调和元素的“源初符文”，以平息大陆躁动的魔法乱流与黑暗侵蚀。",
        appearance="""你拥有精灵的修长体态与尖耳，浅绿眼眸闪动求知欲。披肩银发常被风撩起。淡雅藤蔓纹法袍的下摆沾染着微尘。你珍视的“共鸣水晶木”法杖顶端，嵌着一颗随你调动召唤魔法而变幻色彩的“活体核心”（施法/思考时如呼吸明灭）。腰间多功能皮包装满卷轴碎片、元素罗盘和炼金工具。指尖偶有实验符文荧光或微量冰晶残留。站姿融合了研究者的沉稳与应对魔法反噬的警觉。""",
    )
