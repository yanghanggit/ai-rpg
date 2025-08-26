# from pathlib import Path
from ..models import (
    Boot,
)
from .actor_warrior import create_actor_warrior
from .actor_wizard import create_actor_wizard
from .campaign_setting import FANTASY_WORLD_RPG_CAMPAIGN_SETTING
from .stage_heros_camp import (
    create_demo_heros_camp,
)


#######################################################################################################################
def create_demo_game_world(game_name: str) -> Boot:
    # 创建世界
    world_boot = Boot(
        name=game_name, campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING
    )

    # 创建英雄营地场景和角色
    actor_warrior = create_actor_warrior()
    actor_wizard = create_actor_wizard()
    stage_heros_camp = create_demo_heros_camp()

    # 设置关系和消息
    stage_heros_camp.actors = [actor_warrior, actor_wizard]

    # 设置角色的初始状态
    actor_warrior.kick_off_message += f"""\n注意:{actor_wizard.name} 是你的同伴。你讨厌黑暗元素的法术，因为你认为它们是邪恶的。如果你遇到使用黑暗元素的人，你会毫不犹豫地与之对抗。如果你的同伴使用黑暗元素，你会感到非常愤怒并会与其产生冲突"""
    actor_wizard.kick_off_message += f"""\n注意:{actor_warrior.name} 是你的同伴。你只会召唤魔法，但是召唤出的东西你没法控制，有的时候召唤出很强大的生物，比如巨龙或者巨人，但是你会控制不了而受伤，有的时候召唤出很弱的生物，比如兔子或者蝴蝶，发挥不了作用。你对人类特别有好感，除了喜欢人类的食物外，你还喜欢他们的风土人情，并且你是个话痨，特别喜欢和别人聊天，会不停的问别人问题，如果是人类，你还会主动和他们交谈并一直问有关人类的事情。你说话的语气特别欢快，不时也会说一些笑话来逗别人开心。但是你还有一个不为别人知道的秘密：你深刻理解黑暗元素的力量，但是不会轻易使用它，如果面对你最讨厌的东西——哥布林的时候你会暂时忘记别的魔法，毫不犹豫运用这种黑暗力量将其清除。"""

    # 设置英雄营地场景的初始状态
    world_boot.stages = [stage_heros_camp]

    # 添加世界系统
    world_boot.world_systems = []

    # 返回
    return world_boot


#######################################################################################################################
# def initialize_demo_game_world(game_name: str, write_path: Path) -> Boot:
#     # 写入文件
#     world_boot = create_demo_game_world(game_name)
#     write_path.write_text(world_boot.model_dump_json(), encoding="utf-8")
#     # 返回
#     return world_boot


#######################################################################################################################
