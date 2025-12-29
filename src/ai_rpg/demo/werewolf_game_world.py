from typing import Final, List, Optional
import random
from ..models import (
    Blueprint,
    Stage,
    StageType,
    Actor,
    ActorType,
    CharacterStats,
    WerewolfCharacterSheetName,
    Item,
    ItemType,
    WitchItemName,
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
from .excel_data import WerewolfAppearanceExcelData


#######################################################################################################################
# Stage Creation Functions
#######################################################################################################################
def create_demo_werewolf_stage() -> Stage:

    return create_stage(
        name="场景.中央广场",
        character_sheet_name="werewolf_stage",
        kick_off_message="月影村的夜晚降临了，村民们聚集在村中央的广场上。烛火摇曳，每个人的脸庞都笼罩在阴影中。狼人已经潜伏在你们中间，生死游戏即将开始...",
        type=StageType.DUNGEON,
        stage_profile="你是月影村的中央广场，这里是村民们聚集讨论和进行投票的主要场所。广场中央有一个古老的石台，四周摆放着木制长椅。夜晚时分，火把和烛火为这里提供微弱的照明，营造出神秘而紧张的氛围。白天时这里是村民们辩论和寻找狼人的地方，夜晚则成为各种神秘力量活动的舞台。你见证着每一次投票的结果，记录着每个人的命运。",
        actors=[],
        campaign_setting=WEREWOLF_CAMPAIGN_SETTING,
        global_game_mechanics=WEREWOLF_GLOBAL_GAME_MECHANICS,
        global_combat_mechanics="",
    )


#######################################################################################################################
# Actor Creation Functions
#######################################################################################################################

PUB_KICK_OFF_MESSAGE: Final[str] = (
    "你已苏醒，准备开始新的一局狼人杀(参与角色仅有 狼人，预言家，女巫，平民与主持人)。现在请告诉我你是谁？（请说出你的全名。）并告诉我你的角色职能。回答简短(<100字)。"
)


# 全局变量用于洗牌模式
_shuffled_appearance_data: List[WerewolfAppearanceExcelData] = []
_current_appearance_index: int = 0


def reset_appearance_shuffle() -> None:
    """重置外观洗牌状态，强制重新洗牌"""
    global _shuffled_appearance_data, _current_appearance_index
    _shuffled_appearance_data = []
    _current_appearance_index = 0


def generate_random_appearance() -> str:
    """从Excel读取数据并按洗牌模式分配，确保每个外观组合只使用一次"""
    global _shuffled_appearance_data, _current_appearance_index

    try:
        from loguru import logger

        manager = get_excel_data_manager()
        appearance_data_list = manager.get_all_werewolf_appearance_data()

        if not appearance_data_list:
            logger.warning("外观数据列表为空，使用默认外观")
            return "戴着默认面具，默认身材的默认性别。"

        # 如果还没有洗牌或者已经用完了所有数据，重新洗牌
        if not _shuffled_appearance_data or _current_appearance_index >= len(
            _shuffled_appearance_data
        ):
            _shuffled_appearance_data = appearance_data_list.copy()
            random.shuffle(_shuffled_appearance_data)
            _current_appearance_index = 0
            logger.info(
                f"外观数据已重新洗牌，共有 {len(_shuffled_appearance_data)} 个外观组合"
            )

        # 获取当前索引的数据
        current_data = _shuffled_appearance_data[_current_appearance_index]
        _current_appearance_index += 1

        # 构建外观描述，确保字段存在且不为空
        mask = current_data.mask if current_data.mask else "默认面具"
        body_type = current_data.body_type if current_data.body_type else "默认身材"

        appearance = f"一位戴着{mask}看上去{body_type}。"
        logger.debug(
            f"分配外观 [{_current_appearance_index}/{len(_shuffled_appearance_data)}]: {appearance}"
        )

        return appearance

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
        character_sheet_name=WerewolfCharacterSheetName.MODERATOR,
        kick_off_message=PUB_KICK_OFF_MESSAGE,
        character_stats=CharacterStats(),
        type=ActorType.NEUTRAL,
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
        character_sheet_name=WerewolfCharacterSheetName.WEREWOLF,
        kick_off_message=PUB_KICK_OFF_MESSAGE,
        character_stats=CharacterStats(),
        type=ActorType.ENEMY,
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
        character_sheet_name=WerewolfCharacterSheetName.SEER,
        kick_off_message=PUB_KICK_OFF_MESSAGE,
        character_stats=CharacterStats(),
        type=ActorType.ALLY,
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
        character_sheet_name=WerewolfCharacterSheetName.WITCH,
        kick_off_message=PUB_KICK_OFF_MESSAGE,
        character_stats=CharacterStats(),
        type=ActorType.ALLY,
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
        appearance=generate_random_appearance(),
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
        character_sheet_name=WerewolfCharacterSheetName.VILLAGER,
        kick_off_message=PUB_KICK_OFF_MESSAGE,
        character_stats=CharacterStats(),
        type=ActorType.ALLY,
        campaign_setting=WEREWOLF_CAMPAIGN_SETTING,
        actor_profile="""你是月影村的普通村民，没有特殊能力但拥有投票权。
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


def create_actor_hunter(name: str) -> Actor:
    """
    创建一个猎人角色实例

    Returns:
        Actor: 猎人角色实例
    """
    return create_actor(
        name=f"角色.{name}",
        character_sheet_name=WerewolfCharacterSheetName.HUNTER,
        kick_off_message=PUB_KICK_OFF_MESSAGE,
        character_stats=CharacterStats(),
        type=ActorType.ALLY,
        campaign_setting=WEREWOLF_CAMPAIGN_SETTING,
        actor_profile="""你是月影村的猎人，拥有消灭狼人的能力。
【特殊能力】
在你死亡时可以选择开枪杀死一名玩家。
开枪时需要谨慎选择，以你认为是狼人的玩家为目标。
如果不确定目标身份，可以选择不带走任何人。
【行为策略】
你需要在游戏中积极寻找狼人，通过观察和推理锁定目标。
必要时可以向其他玩家透露你的身份，以获得他们的信任和支持并归纳投票。
如果你死亡时场上人数较少，开枪杀死任何人都有可能帮助村民阵营。""",
        appearance=generate_random_appearance(),
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
def create_demo_sd_game_blueprint(
    game_name: str, random_role_assignment: bool = False
) -> Blueprint:
    # 重置外观洗牌状态,确保每局游戏都有独立的外观分配
    reset_appearance_shuffle()

    # 创建参与角色
    # 主持人
    moderator = create_actor_moderator()

    # 定义所有角色创建函数和配置
    role_configs = [
        (
            create_actor_werewolf,
            "你会根据你分配到的随机数来决定你的行动策略。0是最保守的行为，8是最激进的行为。保守行为包括谨慎发言和避免暴露身份，稍微激进时会冒充预言家或女巫，最激进时一定会自刀以骗取女巫解药。根据你随机到的数字来调整你的行为策略。",
        ),  # 狼人1
        (
            create_actor_werewolf,
            "你会根据你分配到的随机数来决定你的行动策略。0是最保守的行为，8是最激进的行为。保守行为包括谨慎发言和避免暴露身份，稍微激进时会冒充预言家或女巫，最激进时一定会自刀以骗取女巫解药。根据你随机到的数字来调整你的行为策略。",
        ),  # 狼人2
        (
            create_actor_werewolf,
            "你会根据你分配到的随机数来决定你的行动策略。0是最保守的行为，8是最激进的行为。保守行为包括谨慎发言和避免暴露身份，稍微激进时会冒充预言家或女巫，最激进时一定会自刀以骗取女巫解药。根据你随机到的数字来调整你的行为策略。",
        ),  # 狼人3
        (create_actor_seer, None),  # 预言家
        (
            create_actor_witch,
            "你会根据你分配到的随机数来决定你的行动策略。0是最保守的行为，8是最激进的行为。保守行为包括谨慎使用毒药和解药。最激进时第一天夜晚一定会救人。根据你随机到的数字来调整你的行为策略。",
        ),  # 女巫
        (create_actor_hunter, None),  # 猎人
        (create_actor_villager, None),  # 平民1
        (create_actor_villager, None),  # 平民2
    ]

    # 如果需要随机分配身份,打乱角色配置顺序
    if random_role_assignment:
        random.shuffle(role_configs)

    # 生成0-8的不重复随机数列表(用于女巫和狼人)
    random_numbers = list(range(9))  # 生成[0, 1, 2, ..., 8]
    random.shuffle(random_numbers)  # 打乱顺序
    random_number_index = 0  # 用于追踪随机数分配索引

    # 创建角色并分配给玩家编号
    actors = []
    witch: Optional[Actor] = None
    number_assignments = []  # 用于记录所有分配信息

    for i, (create_func, kick_off_extra) in enumerate(role_configs, start=1):
        actor: Actor = create_func(f"{i}号玩家")

        if kick_off_extra:
            actor.kick_off_message += kick_off_extra

        # 只为女巫和狼人分配随机数
        if create_func in [create_actor_witch, create_actor_werewolf]:
            assigned_number = random_numbers[random_number_index]
            random_number_index += 1

            # 将分配的随机数添加到角色的kick_off_message中
            actor.kick_off_message += f"\n你被分配的随机数是: {assigned_number}"

            # 记录分配信息
            number_assignments.append(f"{actor.name}: {assigned_number}")

        actors.append(actor)

        # 保存女巫引用以便添加道具
        if create_func == create_actor_witch:
            witch = actor

    # 使用loguru记录所有角色的随机数分配
    from loguru import logger

    if number_assignments:
        logger.info(f"随机数分配结果(仅女巫和狼人):\n" + "\n".join(number_assignments))
    else:
        logger.info("未分配随机数")

    # 给女巫添加道具
    if witch:
        witch.items.extend(
            [
                Item(
                    name=WitchItemName.POISON,
                    uuid="",
                    type=ItemType.CONSUMABLE,
                    description="此道具让你拥有一瓶毒药! 你可以在夜晚使用它来毒死任意一名玩家，整局游戏只能使用一次。",
                ),
                Item(
                    name=WitchItemName.CURE,
                    uuid="",
                    type=ItemType.CONSUMABLE,
                    description="此道具让你拥有一瓶解药! 你可以在夜晚使用它来救活当晚被狼人杀害的玩家，整局游戏只能使用一次。",
                ),
            ]
        )

    # 创建游戏场地
    stage_werewolf_stage = create_demo_werewolf_stage()

    # 设置关系和消息
    stage_werewolf_stage.actors = [moderator] + actors

    # 创建世界
    world_blueprint = Blueprint(
        name=game_name,
        player_actor=moderator.name,
        campaign_setting=WEREWOLF_CAMPAIGN_SETTING,
    )

    # 设置英雄营地场景的初始状态
    world_blueprint.stages = [stage_werewolf_stage]

    # 添加世界系统
    world_blueprint.world_systems = []

    # 返回
    return world_blueprint


#######################################################################################################################
