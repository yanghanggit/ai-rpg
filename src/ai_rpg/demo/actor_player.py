from ..models import Actor, ActorType, CharacterStats, Skill
from .campaign_setting import (
    FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
    FANTASY_WORLD_RPG_GLOBAL_GAME_MECHANICS,
)
from .utils import (
    create_actor,
)


def create_actor_player() -> Actor:
    """
    创建一个玩家角色实例

    Returns:
        Actor: 玩家角色实例
    """
    player = create_actor(
        name="角色.公会执行官.D",
        character_sheet_name="player",
        kick_off_message="",
        character_stats=CharacterStats(base_max_hp=100),
        type=ActorType.ALLY.value,
        campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
        actor_profile="""你是无意间从现实世界的电脑游戏中穿越到这个世界的玩家D，知道这里不是真实的世界，而是一个由AI生成的奇幻冒险环境。

**输入内容审核规则**:
硬性规则检查，仅拦截以下四类违规：
1. 政治敏感信息
2. 不文明用语
3. 攻击性或侮辱性内容
4. 现实世界或世界观冲突内容：现实世界中的特定专有实体，或与campaign_setting世界观冲突的跨类型元素

**补充说明**:
- 第4条中"特定专有实体"指可被唯一识别的实体；通用概念不属于此类，除非其与campaign_setting的世界观冲突
- 只审核上述四类，不审核合理性、符合度、恰当性、表达方式、情感内容
- 疑问时批准
""",
        appearance="""年轻的人类，体型匀称但不显强壮，皮肤较为白皙。脸上戴着一个银色的金属面具，面具的表情冷峻，在面具之后的眼神中透着一丝异于常人的清明与距离感。身穿深色高领长袍，剪裁合体，胸口别着一枚刻有几何符文的金属徽章，象征公会执行官身份。腰间系着皮质文书袋。双手修长，指尖沾染墨迹，更像学者而非战士。整体装束低调精致，融入这个世界却又保持着某种超然的疏离感。""",
        global_game_mechanics=FANTASY_WORLD_RPG_GLOBAL_GAME_MECHANICS,
    )

    player.skills = [
        Skill(
            name="力量法则",
            description="你了解并能运用这个世界的力量法则，能够通过特定的方式影响物体和环境，甚至改变某些事物的本质属性。",
        ),
    ]

    return player
