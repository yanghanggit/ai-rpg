from ..models import (
    ActorType,
    Actor,
    RPGCharacterProfile,
)
from ..excel_builder.excel_data_manager import excel_data_manager
from .demo_utils import (
    CAMPAIGN_SETTING,
    create_actor,
)


def create_actor_spider() -> Actor:
    """
    创建一个蜘蛛角色实例

    Returns:
        Actor: 蜘蛛角色实例
    """

    actor_data = excel_data_manager.get_actor_data("角色.怪物.蜘蛛-小红")
    assert actor_data is not None, "未找到名为 '角色.怪物.蜘蛛-小红' 的角色数据"

    return create_actor(
        name=actor_data.name,
        character_sheet_name=actor_data.character_sheet_name,
        kick_off_message="",
        rpg_character_profile=RPGCharacterProfile(base_dexterity=1),
        type=ActorType.MONSTER,
        campaign_setting=CAMPAIGN_SETTING,
        actor_profile=actor_data.actor_profile,
        appearance=actor_data.appearance,
    )
