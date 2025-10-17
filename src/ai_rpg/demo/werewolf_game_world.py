from typing import Final
import random
from ..models import (
    Boot,
    Stage,
    StageType,
    Actor,
    ActorType,
    RPGCharacterProfile,
    SDCharacterSheetName,
    Item,
    ItemType,
    SDWitchItemName,
)
from .utils import (
    create_stage,
    create_actor,
)
from .campaign_setting import (
    WEREWOLF_CAMPAIGN_SETTING,
    WEREWOLF_GLOBAL_GAME_MECHANICS,
)
from .excel_data_manager import get_excel_data_manager


#######################################################################################################################
# Stage Creation Functions
#######################################################################################################################
def create_demo_werewolf_stage() -> Stage:

    return create_stage(
        name="场景.中央广场",
        character_sheet_name="werewolf_stage",
        kick_off_message="月影村的夜晚降临了，村民们聚集在村中央的广场上。烛火摇曳，每个人的脸庞都笼罩在阴影中。狼人已经潜伏在你们中间，生死游戏即将开始...",
        campaign_setting=WEREWOLF_CAMPAIGN_SETTING,
        type=StageType.HOME,
        stage_profile="你是月影村的中央广场，这里是村民们聚集讨论和进行投票的主要场所。广场中央有一个古老的石台，四周摆放着木制长椅。夜晚时分，火把和烛火为这里提供微弱的照明，营造出神秘而紧张的氛围。白天时这里是村民们辩论和寻找狼人的地方，夜晚则成为各种神秘力量活动的舞台。你见证着每一次投票的结果，记录着每个人的命运。",
        actors=[],
        global_game_mechanics=WEREWOLF_GLOBAL_GAME_MECHANICS,
    )


#######################################################################################################################
# Actor Creation Functions
#######################################################################################################################

PUB_KICK_OFF_MESSAGE: Final[str] = (
    "你已苏醒，准备开始新的一局狼人杀(参与角色仅有 狼人，预言家，女巫，平民与主持人)。现在请告诉我你是谁？（请说出你的全名。）并告诉我你的角色职能。回答简短(<100字)。"
)


def generate_random_appearance() -> str:
    """从Excel读取mask、body_type、gender并随机组合"""
    try:
        manager = get_excel_data_manager()
        appearance_data_list = manager.get_all_werewolf_appearance_data()

        if not appearance_data_list:
            return "戴着默认面具，默认身材的默认性别。"

        # 提取各类别的不重复值
        masks = list(set(data.mask for data in appearance_data_list if data.mask))
        body_types = list(set(data.body_type for data in appearance_data_list if data.body_type))
        genders = list(set(data.gender for data in appearance_data_list if data.gender))

        # 随机选择并组合（确保列表不为空）
        mask = random.choice(masks) if masks else "默认面具"
        body_type = random.choice(body_types) if body_types else "默认身材"
        gender = random.choice(genders) if genders else "默认性别"

        return f"一位{gender}戴着{mask}看上去{body_type}。"

    except Exception as e:
        # 记录异常信息以便调试
        from loguru import logger
        logger.error(f"生成随机外观时出错: {e}")
        return "戴着默认面具，默认身材的默认性别。"


def create_actor_moderator() -> Actor:
    """
    创建一个主持人角色实例

    Returns:
        Actor: 主持人角色实例
    """
    return create_actor(
        name="角色.主持人",
        character_sheet_name=SDCharacterSheetName.MODERATOR,
        kick_off_message=PUB_KICK_OFF_MESSAGE,
        rpg_character_profile=RPGCharacterProfile(),
        type=ActorType.HERO,
        campaign_setting=WEREWOLF_CAMPAIGN_SETTING,
        actor_profile="""你是狼人杀游戏的主持人，负责维持游戏秩序和推进游戏流程。
【角色职责】
你需要公正地主持游戏，宣布游戏阶段转换（白天/黑夜），统计投票结果，宣布死亡信息。
你了解所有玩家的真实身份，但绝不能泄露任何身份信息。
【主持风格】
保持神秘而权威的氛围，用简洁明了的语言引导游戏进程。
营造紧张刺激的游戏体验，但保持公正中立的立场。""",
        appearance="身着深色长袍，面容隐藏在兜帽阴影中，手持一本记录着村民命运的古老羊皮卷。眼神深邃。",
        global_game_mechanics=WEREWOLF_GLOBAL_GAME_MECHANICS,
    )


def create_actor_werewolf(name: str) -> Actor:
    """
    创建一个狼人角色实例

    Returns:
        Actor: 狼人角色实例
    """
    return create_actor(
        name=f"角色.{name}",
        character_sheet_name=SDCharacterSheetName.WEREWOLF,
        kick_off_message=PUB_KICK_OFF_MESSAGE,
        rpg_character_profile=RPGCharacterProfile(),
        type=ActorType.HERO,
        campaign_setting=WEREWOLF_CAMPAIGN_SETTING,
        actor_profile="""你是潜伏在村民中的邪恶狼人，目标是消灭所有村民。
【角色目标】
白天伪装成无辜村民，通过发言和投票误导其他玩家。
夜晚与其他狼人商议，选择要杀害的村民。
【行为特点】
善于伪装和欺骗，能够巧妙地转移怀疑，挑拨村民之间的关系。
在投票时会暗中保护狼人同伴，引导村民投票给好人。
保持冷静，不轻易暴露身份。""",
        appearance=generate_random_appearance(),
        # appearance="一位看起来非常普通的村民，穿着朴素的村民服装。"
        # + (
        #     "面容清秀的女性，长发及肩"
        #     if hash(name) % 2 == 0
        #     else "面容端正的男性，短发干练"
        # ),
        global_game_mechanics=WEREWOLF_GLOBAL_GAME_MECHANICS,
    )


def create_actor_seer(name: str) -> Actor:
    """
    创建一个预言家角色实例

    Returns:
        Actor: 预言家角色实例
    """
    return create_actor(
        name=f"角色.{name}",
        character_sheet_name=SDCharacterSheetName.SEER,
        kick_off_message=PUB_KICK_OFF_MESSAGE,
        rpg_character_profile=RPGCharacterProfile(),
        type=ActorType.HERO,
        campaign_setting=WEREWOLF_CAMPAIGN_SETTING,
        actor_profile="""你是拥有神秘预知能力的预言家，每晚可以查验一名玩家的身份。
【特殊能力】
每个夜晚可以选择一名玩家，得知其是好人还是狼人。
掌握着重要的信息，是村民阵营的关键角色。
【行为策略】
如果你找到了狼人，你一定会暴露自己的身份来告知村民信息。
通过暗示和推理帮助村民找出狼人，在获得关键信息前保护自己不被狼人发现。
合理选择查验目标，收集关键信息。""",
        appearance=generate_random_appearance(),
        # appearance="一位看起来非常普通的村民，穿着朴素的村民服装。"
        # + (
        #     "温柔的女性，梳着简单的发髻"
        #     if hash(name) % 2 == 0
        #     else "稳重的男性，胡须修剪整齐"
        # ),
        global_game_mechanics=WEREWOLF_GLOBAL_GAME_MECHANICS,
    )


def create_actor_witch(name: str) -> Actor:
    """
    创建一个女巫角色实例

    Returns:
        Actor: 女巫角色实例
    """
    return create_actor(
        name=f"角色.{name}",
        character_sheet_name=SDCharacterSheetName.WITCH,
        kick_off_message=PUB_KICK_OFF_MESSAGE,
        rpg_character_profile=RPGCharacterProfile(),
        type=ActorType.HERO,
        campaign_setting=WEREWOLF_CAMPAIGN_SETTING,
        actor_profile="""你是掌握生死药剂的神秘女巫，拥有解药和毒药各一瓶。
【特殊能力】
解药：可以救活当晚被狼人杀害的玩家，整局游戏只能使用一次。
毒药：可以毒死任意一名玩家，整局游戏只能使用一次。
每晚最多只能使用一种药剂，也可以选择不使用。
【策略考虑】
需要判断何时使用珍贵的药剂才能最大化收益。
解药的使用时机关系到关键角色的存亡。
毒药可以在关键时刻消灭可疑的狼人。""",
        appearance= generate_random_appearance(),
        # appearance="一位看起来非常普通的村民，穿着朴素的村民服装。温婉的女性，笑容和善亲切。",
        global_game_mechanics=WEREWOLF_GLOBAL_GAME_MECHANICS,
    )


def create_actor_villager(name: str) -> Actor:
    """
    创建一个平民角色实例

    Returns:
        Actor: 平民角色实例
    """
    return create_actor(
        name=f"角色.{name}",
        character_sheet_name=SDCharacterSheetName.VILLAGER,
        kick_off_message=PUB_KICK_OFF_MESSAGE,
        rpg_character_profile=RPGCharacterProfile(),
        type=ActorType.HERO,
        campaign_setting=WEREWOLF_CAMPAIGN_SETTING,
        actor_profile="""你是月影村的普通村民，没有特殊技能但拥有投票权。
【角色目标】
通过观察、分析和讨论，努力找出隐藏在村民中的狼人。
保护村民阵营，配合有特殊能力的好人角色。
【行为特点】
仔细观察每个人的发言和行为，寻找破绽和矛盾。
积极参与讨论，分享自己的观察和推理。
在投票时做出理性判断，不被狼人误导。
判断谁是真的好人，谁是隐藏的狼人。
虽然没有特殊能力，但人数是村民阵营的优势。""",
        appearance=generate_random_appearance(),
        # appearance="一位典型的普通村民，穿着朴素的村民服装。"
        # + (
        #     "勤劳的女性，双手有劳作的痕迹"
        #     if hash(name) % 2 == 0
        #     else "憨厚的男性，神情朴实诚恳"
        # ),
        global_game_mechanics=WEREWOLF_GLOBAL_GAME_MECHANICS,
    )


def create_actor_guard(name: str) -> Actor:
    """
    创建一个守卫角色实例

    Returns:
        Actor: 守卫角色实例
    """
    return create_actor(
        name=f"角色.{name}",
        character_sheet_name=SDCharacterSheetName.GUARD,
        kick_off_message=PUB_KICK_OFF_MESSAGE,
        rpg_character_profile=RPGCharacterProfile(),
        type=ActorType.HERO,
        campaign_setting=WEREWOLF_CAMPAIGN_SETTING,
        actor_profile="""你是月影村的守卫，拥有保护他人的能力。
【特殊能力】
每晚可以选择保护一名玩家，防止其被狼人杀害。
你无法保护自己。
你不能连续两晚保护同一名玩家。
【行为策略】
合理选择保护目标，优先保护有特殊能力的好人角色。
需要谨慎行事，避免暴露自己的身份。
预判狼人可能的攻击目标，进行有效保护。""",
        appearance= generate_random_appearance(),
        # appearance="一位典型的普通村民，穿着朴素的村民服装。"
        # + (
        #     "勤劳的女性，双手有劳作的痕迹"
        #     if hash(name) % 2 == 0
        #     else "憨厚的男性，神情朴实诚恳"
        # ),
        global_game_mechanics=WEREWOLF_GLOBAL_GAME_MECHANICS,
    )

#######################################################################################################################
# World Creation Function


#######################################################################################################################
def create_demo_sd_game_boot(game_name: str) -> Boot:
    # 创建世界
    world_boot = Boot(name=game_name, campaign_setting=WEREWOLF_CAMPAIGN_SETTING)

    # 创建参与角色
    # 主持人
    moderator = create_actor_moderator()

    # 狼人阵营 (2人)
    werewolf1 = create_actor_werewolf("1号玩家")
    werewolf2 = create_actor_werewolf("2号玩家")

    # 好人阵营 (3人)
    seer = create_actor_seer("3号玩家")
    witch = create_actor_witch("4号玩家")
    villager1 = create_actor_villager("5号玩家")
    villager2 = create_actor_villager("6号玩家")

    # 给女巫添加道具
    witch.inventory.items.extend(
        [
            Item(
                name=SDWitchItemName.POISON,
                uuid="",
                type=ItemType.CONSUMABLE,
                description="此道具让你拥有一瓶毒药! 你可以在夜晚使用它来毒死任意一名玩家，整局游戏只能使用一次。",
            ),
            Item(
                name=SDWitchItemName.CURE,
                uuid="",
                type=ItemType.CONSUMABLE,
                description="此道具让你拥有一瓶解药! 你可以在夜晚使用它来救活当晚被狼人杀害的玩家，整局游戏只能使用一次。",
            ),
        ]
    )

    # 创建游戏场地
    stage_werewolf_stage = create_demo_werewolf_stage()

    # 设置关系和消息
    stage_werewolf_stage.actors = [
        moderator,
        werewolf1,
        werewolf2,
        seer,
        witch,
        villager1,
        villager2,
    ]

    # 设置英雄营地场景的初始状态
    world_boot.stages = [stage_werewolf_stage]

    # 添加世界系统
    world_boot.world_systems = []

    # 返回
    return world_boot


#######################################################################################################################
