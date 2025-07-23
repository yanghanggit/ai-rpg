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
    create_world_system,
)
import copy
from multi_agents_game.demo.actor_warrior import actor_warrior
from multi_agents_game.demo.actor_wizard import actor_wizard

#######################################################################################################################################
#######################################################################################################################################
#######################################################################################################################################
test_world_system = create_world_system(
    name="系统.世界系统",
    kick_off_message=f"""你已苏醒，准备开始冒险。请告诉我你的职能和目标。""",
    campaign_setting=CAMPAIGN_SETTING,
    world_system_profile="你是一个测试的系统。用于生成魔法",
)
#######################################################################################################################################
#######################################################################################################################################
#######################################################################################################################################

# 创建世界
world_boot = Boot(name="", campaign_setting=CAMPAIGN_SETTING)

world_boot.stages = [
    stage_heros_camp,
]

world_boot.world_systems = []

actor_warrior.kick_off_message += f"""\n注意:{actor_wizard.name} 是你的同伴。你目前只会使用防御类的技能！你讨厌黑暗法术，因为你认为它们是邪恶的。"""
actor_wizard.kick_off_message += f"""\n注意:{actor_warrior.name} 是你的同伴。你最擅长的是火焰类的魔法，而且你还有一个不为别人知道的秘密：你深刻理解黑暗元素的力量，但是不会轻易使用它，如果面对你最讨厌的东西——哥布林的时候你会毫不犹豫运用这种禁忌之力将其清除。"""


#######################################################################################################################################
#######################################################################################################################################
#######################################################################################################################################
def setup_demo_game_world(game_name: str, write_path: Path) -> Optional[Boot]:

    try:

        global world_boot

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
