from pathlib import Path
from loguru import logger
from ..models import (
    Boot,
)

from .stage_heros_camp import (
    create_demo_heros_camp,
)

from typing import Optional
from .demo_utils import (
    CAMPAIGN_SETTING,
)
from ..demo.actor_warrior import create_actor_warrior
from ..demo.actor_wizard import create_actor_wizard


#######################################################################################################################################
#######################################################################################################################################
#######################################################################################################################################
def setup_demo_game_world(game_name: str, write_path: Path) -> Optional[Boot]:

    try:

        # 创建世界
        world_boot = Boot(name=game_name, campaign_setting=CAMPAIGN_SETTING)

        actor_warrior = create_actor_warrior()
        actor_wizard = create_actor_wizard()
        stage_heros_camp = create_demo_heros_camp()

        # 设置关系和消息
        stage_heros_camp.actors = [actor_warrior, actor_wizard]
        actor_warrior.kick_off_message += f"""\n注意:{actor_wizard.name} 是你的同伴。你目前只会使用防御类的技能！你讨厌黑暗法术，因为你认为它们是邪恶的。"""
        actor_wizard.kick_off_message += f"""\n注意:{actor_warrior.name} 是你的同伴。你最擅长的是火焰类的魔法，而且你还有一个不为别人知道的秘密：你深刻理解黑暗元素的力量，但是不会轻易使用它，如果面对你最讨厌的东西——哥布林的时候你会毫不犹豫运用这种禁忌之力将其清除。"""
        # 复制世界设置
        world_boot.stages = [stage_heros_camp]

        # 添加系统
        world_boot.world_systems = []

        # 写入文件
        write_path.write_text(world_boot.model_dump_json(), encoding="utf-8")

        # 返回
        return world_boot

    except Exception as e:
        logger.error(f"An error occurred: {e}")

    return None
