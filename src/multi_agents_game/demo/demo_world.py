from pathlib import Path
from loguru import logger
from ..models import (
    Boot,
)

from .stage_heros_camp import (
    stage_heros_camp,
)

from typing import Optional
from ..game.tcg_game_demo_utils import (
    CAMPAIGN_SETTING,
)
import copy
from ..demo.actor_warrior import actor_warrior
from ..demo.actor_wizard import actor_wizard

#######################################################################################################################################
#######################################################################################################################################
#######################################################################################################################################

# 创建世界
# world_boot = Boot(name="", campaign_setting=CAMPAIGN_SETTING)

# world_boot.stages = [
#     stage_heros_camp,
# ]

# world_boot.world_systems = []

# stage_heros_camp.actors = [actor_warrior, actor_wizard]
# actor_warrior.kick_off_message += f"""\n注意:{actor_wizard.name} 是你的同伴。你目前只会使用防御类的技能！你讨厌黑暗法术，因为你认为它们是邪恶的。"""
# actor_wizard.kick_off_message += f"""\n注意:{actor_warrior.name} 是你的同伴。你最擅长的是火焰类的魔法，而且你还有一个不为别人知道的秘密：你深刻理解黑暗元素的力量，但是不会轻易使用它，如果面对你最讨厌的东西——哥布林的时候你会毫不犹豫运用这种禁忌之力将其清除。"""


#######################################################################################################################################
#######################################################################################################################################
#######################################################################################################################################
def setup_demo_game_world(game_name: str, write_path: Path) -> Optional[Boot]:

    try:

        # 创建世界
        world_boot = Boot(name="", campaign_setting=CAMPAIGN_SETTING)

        # 创建stage和actors的副本以避免修改原始对象
        stage_copy = copy.deepcopy(stage_heros_camp)
        warrior_copy = copy.deepcopy(actor_warrior)
        wizard_copy = copy.deepcopy(actor_wizard)

        # 设置关系和消息
        stage_copy.actors = [warrior_copy, wizard_copy]
        warrior_copy.kick_off_message += f"""\n注意:{wizard_copy.name} 是你的同伴。你目前只会使用防御类的技能！你讨厌黑暗法术，因为你认为它们是邪恶的。"""
        wizard_copy.kick_off_message += f"""\n注意:{warrior_copy.name} 是你的同伴。你最擅长的是火焰类的魔法，而且你还有一个不为别人知道的秘密：你深刻理解黑暗元素的力量，但是不会轻易使用它，如果面对你最讨厌的东西——哥布林的时候你会毫不犹豫运用这种禁忌之力将其清除。"""

        world_boot.stages = [stage_copy]
        world_boot.world_systems = []

        create_new_world = copy.deepcopy(world_boot)
        create_new_world.name = game_name

        # 写入文件
        write_path.write_text(create_new_world.model_dump_json(), encoding="utf-8")

        # 返回
        return create_new_world

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        # return None

    # assert False, "Should not reach here"
    return None


#######################################################################################################################################
#######################################################################################################################################
#######################################################################################################################################
