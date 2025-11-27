import os
import sys

# 将 src 目录添加到模块搜索路径
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

from typing import Dict, List, Set, TypedDict, cast
from loguru import logger
from ai_rpg.chat_services.client import ChatClient
from ai_rpg.configuration import (
    server_configuration,
)
from ai_rpg.game.config import GLOBAL_TCG_GAME_NAME, setup_logger
from ai_rpg.demo import (
    create_actor_warrior,
    create_demo_dungeon5,
    create_demo_game_world_boot2,
)
from ai_rpg.game.player_session import PlayerSession
from ai_rpg.game.tcg_game import (
    TCGGame,
)
from ai_rpg.game.game_data_service import (
    get_user_world_data,
    delete_user_world_data,
)
from ai_rpg.models import (
    CombatResult,
    World,
    AllyComponent,
    PlayerComponent,
    PlanAction,
    HomeComponent,
    TransStageAction,
)
from ai_rpg.services.home_actions import (
    activate_speak_action,
)
from ai_rpg.services.dungeon_actions import (
    activate_actor_card_draws,
    activate_random_play_cards,
)
from ai_rpg.services.dungeon_stage_transition import (
    initialize_dungeon_first_entry,
    advance_to_next_stage,
    complete_dungeon_and_return_home,
)

import datetime


############################################################################################################
############################################################################################################
############################################################################################################
class SpeakCommand(TypedDict):
    target: str
    content: str


############################################################################################################
############################################################################################################
############################################################################################################
class PlayCardsCommand(TypedDict):
    params: Dict[str, str]  # 卡牌名称 -> 目标名称


############################################################################################################
############################################################################################################
############################################################################################################
class HeroPlanCommand(TypedDict):
    heroes: List[str]  # 英雄列表


############################################################################################################
############################################################################################################
############################################################################################################
class HomeTransStageCommand(TypedDict):
    stage_name: str  # 目标场景名称


############################################################################################################
############################################################################################################
############################################################################################################
def _parse_user_action_input(usr_input: str, keys: Set[str]) -> Dict[str, str]:

    ret: Dict[str, str] = {}
    try:
        parts = usr_input.split("--")
        args = {}
        for part in parts:
            if "=" in part:
                # 使用 maxsplit=1 确保只在第一个等号处分割
                key_value = part.split("=", 1)
                if len(key_value) == 2:
                    key = key_value[0].strip()
                    value = key_value[1].strip()
                    args[key] = value

        for key in keys:
            if key in args:
                ret[key] = args[key]

    except Exception as e:
        logger.error(f" {usr_input}, 解析输入时发生错误: {e}")

    return ret


############################################################################################################
############################################################################################################
############################################################################################################
# sample: /speak --target=角色.法师.奥露娜 --content=我还是需要准备一下
def _parse_speak_command_input(usr_input: str) -> SpeakCommand:
    """
    解析用户输入的说话命令，提取目标角色和说话内容。

    该函数专门处理游戏中的角色对话命令，支持两种命令格式：
    - /speak：完整的说话命令
    - /ss：说话命令的简写形式

    Args:
        usr_input (str): 用户输入的原始字符串，应包含说话命令及其参数

    Returns:
        SpeakCommand: 包含以下字段的类型化字典：
            - target (str): 目标角色的名称或路径，如果未找到则为空字符串
            - content (str): 要说的内容，如果未找到则为空字符串

    Command Format:
        /speak --target=<角色名称> --content=<说话内容>
        /ss --target=<角色名称> --content=<说话内容>

    Examples:
        >>> _parse_speak_command_input("/speak --target=角色.法师.奥露娜 --content=我还是需要准备一下")
        {'target': '角色.法师.奥露娜', 'content': '我还是需要准备一下'}

        >>> _parse_speak_command_input("/ss --target=玩家 --content=你好")
        {'target': '玩家', 'content': '你好'}

        >>> _parse_speak_command_input("/move --direction=north")  # 非说话命令
        {'target': '', 'content': ''}

    Note:
        - 如果输入不包含 /speak 或 /ss 命令，函数将返回空的 SpeakCommand
        - 参数解析失败时，相应字段将保持为空字符串
        - 依赖于 _parse_user_action_input 函数进行实际的参数解析
    """
    ret: SpeakCommand = {"target": "", "content": ""}
    if "/speak" in usr_input or "/ss" in usr_input:
        return cast(
            SpeakCommand, _parse_user_action_input(usr_input, {"target", "content"})
        )

    return ret


###############################################################################################################################################
# sample: /play-cards --params=火球术=敌人.哥布林;治疗术=自己
def _parse_play_cards_command_input(usr_input: str) -> PlayCardsCommand:
    """
    解析用户输入的打牌命令，提取卡牌使用参数。

    该函数专门处理游戏中的卡牌使用命令，支持两种命令格式：
    - /play-cards：完整的打牌命令
    - /pc：打牌命令的简写形式（在其他地方使用）

    Args:
        usr_input (str): 用户输入的原始字符串，应包含打牌命令及其参数

    Returns:
        PlayCardsCommand: 包含以下字段的类型化字典：
            - params (Dict[str, str]): 卡牌名称到目标的映射字典
                如果未找到有效参数则为空字典

    Command Format:
        /play-cards --params=<卡牌1>=<目标1>;<卡牌2>=<目标2>;...

    参数格式说明：
        - 使用分号(;)分隔多个卡牌-目标对
        - 使用等号(=)连接卡牌名称和目标
        - 卡牌名称：如"火球术"、"治疗术"等
        - 目标名称：如"敌人.哥布林"、"自己"、"队友.法师"等

    Examples:
        >>> _parse_play_cards_command_input("/play-cards --params=火球术=敌人.哥布林;治疗术=自己")
        {'params': {'火球术': '敌人.哥布林', '治疗术': '自己'}}

        >>> _parse_play_cards_command_input("/play-cards --params=闪电链=敌人.哥布林")
        {'params': {'闪电链': '敌人.哥布林'}}

        >>> _parse_play_cards_command_input("/speak --target=玩家 --content=你好")  # 非打牌命令
        {'params': {}}

    Note:
        - 如果输入不包含 /play-cards 命令，函数将返回空的 PlayCardsCommand
        - 参数解析失败时，params 字段将保持为空字典
        - 依赖于 _parse_user_action_input 函数进行基础参数解析
        - 对 params 参数进行特殊的键值对解析处理
    """
    ret: PlayCardsCommand = {"params": {}}

    if "/play-cards" in usr_input or "/pc" in usr_input:
        # 使用基础解析函数获取 params 字符串
        parsed_args = _parse_user_action_input(usr_input, {"params"})

        if "params" in parsed_args and parsed_args["params"]:
            try:
                # 解析 params 字符串：火球术=敌人.哥布林;治疗术=自己
                params_str = parsed_args["params"]
                card_target_pairs = params_str.split(";")

                params_dict = {}
                for pair in card_target_pairs:
                    if "=" in pair:
                        card_name, target = pair.split(
                            "=", 1
                        )  # 使用 maxsplit=1 防止目标名称中包含=
                        params_dict[card_name.strip()] = target.strip()

                ret["params"] = params_dict

            except Exception as e:
                logger.error(f"解析打牌命令参数时发生错误: {usr_input}, 错误: {e}")

    return ret


###############################################################################################################################################
# sample: /hero --params=角色.法师.奥露娜;角色.战士.卡恩
def _parse_hero_plan_command_input(usr_input: str) -> HeroPlanCommand:
    """
    解析用户输入的英雄命令，提取英雄列表参数。

    该函数专门处理游戏中的英雄选择命令，支持两种命令格式：
    - /hero：完整的英雄命令
    - /h：英雄命令的简写形式

    Args:
        usr_input (str): 用户输入的原始字符串，应包含英雄命令及其参数

    Returns:
        HeroCommand: 包含以下字段的类型化字典：
            - heroes (list[str]): 英雄名称列表，如果未找到有效参数则为空列表

    Command Format:
        /hero --params=<英雄1>;<英雄2>;<英雄3>;...

    参数格式说明：
        - 使用分号(;)分隔多个英雄名称
        - 英雄名称格式：如"角色.法师.奥露娜"、"角色.战士.卡恩"等
        - 支持完整的角色路径格式

    Examples:
        >>> _parse_hero_command_input("/hero --params=角色.法师.奥露娜;角色.战士.卡恩")
        {'heroes': ['角色.法师.奥露娜', '角色.战士.卡恩']}

        >>> _parse_hero_command_input("/h --params=角色.盗贼.艾琳")
        {'heroes': ['角色.盗贼.艾琳']}

        >>> _parse_hero_command_input("/speak --target=玩家 --content=你好")  # 非英雄命令
        {'heroes': []}

    Note:
        - 如果输入不包含 /hero 或 /h 命令，函数将返回空的 HeroCommand
        - 参数解析失败时，heroes 字段将保持为空列表
        - 依赖于 _parse_user_action_input 函数进行基础参数解析
        - 对 params 参数进行特殊的英雄列表解析处理
        - 会自动过滤掉空的英雄名称
    """
    ret: HeroPlanCommand = {"heroes": []}

    if "/hero" in usr_input or "/ho" in usr_input:
        # 使用基础解析函数获取 params 字符串
        parsed_args = _parse_user_action_input(usr_input, {"params"})

        if "params" in parsed_args and parsed_args["params"]:
            try:
                # 解析 params 字符串：角色.法师.奥露娜;角色.战士.卡恩
                params_str = parsed_args["params"]
                hero_names = params_str.split(";")

                # 过滤空字符串并去除首尾空格
                heroes_list = [hero.strip() for hero in hero_names if hero.strip()]
                ret["heroes"] = heroes_list

            except Exception as e:
                logger.error(f"解析英雄命令参数时发生错误: {usr_input}, 错误: {e}")

    return ret


###############################################################################################################################################
# sample: /trans_home --params=场景.营地
def _parse_home_trans_stage_command_input(usr_input: str) -> HomeTransStageCommand:
    """
    解析用户输入的家园传送命令，提取目标场景名称。

    该函数专门处理游戏中的家园场景传送命令，支持两种命令格式：
    - /trans_home：完整的家园传送命令
    - /th：家园传送命令的简写形式

    Args:
        usr_input (str): 用户输入的原始字符串，应包含家园传送命令及其参数

    Returns:
        HomeTransStageCommand: 包含以下字段的类型化字典：
            - stage_name (str): 目标场景名称，如果未找到有效参数则为空字符串

    Command Format:
        /trans_home --params=<目标场景名称>

    参数格式说明：
        - 场景名称格式：如"场景.营地"、"场景.训练场"等
        - 支持完整的场景路径格式

    Examples:
        >>> _parse_home_trans_stage_command_input("/trans_home --params=场景.营地")
        {'stage_name': '场景.营地'}

        >>> _parse_home_trans_stage_command_input("/th --params=场景.训练场")
        {'stage_name': '场景.训练场'}

        >>> _parse_home_trans_stage_command_input("/speak --target=玩家 --content=你好")  # 非传送命令
        {'stage_name': ''}

    Note:
        - 如果输入不包含 /trans_home 或 /th 命令，函数将返回空的 HomeTransStageCommand
        - 参数解析失败时，stage_name 字段将保持为空字符串
        - 依赖于 _parse_user_action_input 函数进行基础参数解析
        - 对 params 参数进行场景名称解析处理
    """
    ret: HomeTransStageCommand = {"stage_name": ""}

    if "/trans_home" in usr_input or "/th" in usr_input:
        # 使用基础解析函数获取 params 字符串
        parsed_args = _parse_user_action_input(usr_input, {"params"})

        if "params" in parsed_args and parsed_args["params"]:
            try:
                # 解析 params 字符串：场景.营地
                stage_name = parsed_args["params"].strip()
                if stage_name:
                    ret["stage_name"] = stage_name

            except Exception as e:
                logger.error(f"解析家园传送命令参数时发生错误: {usr_input}, 错误: {e}")

    return ret


#######################################################################################################################################
# TODO, 临时添加行动, 逻辑。
def _plan_action(terminal_game: TCGGame, actors: List[str]) -> None:

    for actor_name in actors:

        actor_entity = terminal_game.get_actor_entity(actor_name)
        # assert actor_entity is not None
        if actor_entity is None:
            logger.error(f"角色: {actor_name} 不存在！")
            continue

        if not actor_entity.has(AllyComponent):
            logger.error(f"角色: {actor_name} 不是英雄，不能有行动计划！")
            continue

        if actor_entity.has(PlayerComponent):
            logger.error(f"角色: {actor_name} 是玩家控制的，不能有行动计划！")
            continue

        logger.debug(f"为角色: {actor_name} 激活行动计划！")
        actor_entity.replace(PlanAction, actor_entity.name)


#######################################################################################################################################
# TODO, 临时添加行动, 逻辑。
def _trans_stage_action(terminal_game: TCGGame, stage_name: str) -> bool:
    target_stage_entity = terminal_game.get_stage_entity(stage_name)
    # assert target_stage_entity is not None, f"目标场景: {stage_name} 不存在！"
    if target_stage_entity is None:
        logger.error(f"目标场景: {stage_name} 不存在！")
        return False

    assert target_stage_entity.has(HomeComponent), f"目标场景: {stage_name} 不是家园！"
    player_entity = terminal_game.get_player_entity()
    assert player_entity is not None, "玩家实体不存在！"
    player_entity.replace(TransStageAction, player_entity.name, stage_name)
    return True


###############################################################################################################################################
async def _run_game(
    user: str,
    game: str,
    actor: str,
) -> None:

    # 注意，如果确定player是固定的，但是希望每次玩新游戏，就调用这句。
    # 或者，换成random_name，随机生成一个player名字。
    delete_user_world_data(user, GLOBAL_TCG_GAME_NAME)

    # 先检查一下world_data是否存在
    world_exists = get_user_world_data(user, game)

    #
    if world_exists is None:

        # 获取world_boot_data
        world_boot = create_demo_game_world_boot2(game)
        # create_demo_game_world_boot1(game)  # TODO，临时修改，快速测试！
        # get_game_boot_data(game)
        assert world_boot is not None, "WorldBootDocument 反序列化失败"

        # 如果world不存在，说明是第一次创建游戏
        world_exists = World(boot=world_boot)

        # 运行时生成地下城系统
        # world_exists.dungeon = create_demo_dungeon6()
        world_exists.dungeon = create_demo_dungeon5()

    else:
        logger.info(f"恢复游戏: {user}, {game}")

    # 依赖注入，创建新的游戏
    assert world_exists is not None, "World data must exist to create a game"
    terminal_game = TCGGame(
        name=game,
        player_session=PlayerSession(
            name=user,
            actor=actor,
            game=game,
        ),
        world=world_exists,
    )

    # 初始化聊天客户端
    ChatClient.initialize_url_config(server_configuration)

    # 启动游戏的判断，是第一次建立还是恢复？
    if len(terminal_game.world.entities_serialization) == 0:
        logger.info(f"游戏中没有实体 = {game}, 说明是第一次创建游戏")
        # 直接构建ecs
        terminal_game.new_game().save()

    else:
        logger.warning(f"游戏中有实体 = {game}，需要通过数据恢复实体，是游戏回复的过程")
        # 测试！回复ecs
        terminal_game.load_game().save()

    # 测试一下玩家控制角色，如果没有就是错误。
    player_entity = terminal_game.get_player_entity()
    if player_entity is None:
        logger.error(f"玩家实体不存在 = {user}, {game}, {actor}")
        exit(1)

    # 初始化！
    await terminal_game.initialize()

    # 主循环
    while True:

        await _process_player_input(terminal_game)
        if terminal_game.should_terminate:
            break

    # 会保存一下。
    terminal_game.save()

    # 退出游戏
    terminal_game.exit()

    # 退出
    exit(0)


###############################################################################################################################################
async def _process_dungeon_state_input(terminal_game: TCGGame, usr_input: str) -> None:
    """处理地下城状态下的玩家输入"""

    if usr_input == "/dc" or usr_input == "/draw-cards":

        if not terminal_game.current_combat_sequence.is_ongoing:
            logger.error(f"{usr_input} 只能在战斗中使用is_on_going_phase")
            return

        logger.debug(f"玩家输入 = {usr_input}, 准备抽卡")
        activate_actor_card_draws(terminal_game)

        await terminal_game.combat_pipeline.process()

    elif usr_input == "/pc" or "/play-cards" in usr_input:

        if not terminal_game.current_combat_sequence.is_ongoing:
            logger.error(f"{usr_input} 只能在战斗中使用is_on_going_phase")
            return

        # 统一解析卡牌命令（/pc 和 /play-cards 都用同样的逻辑处理）
        player_cards_command = _parse_play_cards_command_input(usr_input)
        logger.debug(
            f"玩家输入 = {usr_input}, 解析到的卡牌命令: {player_cards_command}"
        )

        # 执行打牌行动（现在使用随机选行动）
        if activate_random_play_cards(terminal_game):
            await terminal_game.combat_pipeline.process()

    elif usr_input == "/rth" or usr_input == "/return-to-home":

        if (
            len(terminal_game.current_combat_sequence.combats) == 0
            or not terminal_game.current_combat_sequence.is_waiting
        ):
            logger.error(f"{usr_input} 只能在战斗后使用!!!!!")
            return

        logger.debug(f"玩家输入 = {usr_input}, 准备传送回家")
        complete_dungeon_and_return_home(terminal_game)

    elif usr_input == "/and" or usr_input == "/advance-next-dungeon":

        if terminal_game.current_combat_sequence.is_waiting:
            if (
                terminal_game.current_combat_sequence.current_result
                == CombatResult.HERO_WIN
            ):

                next_level = terminal_game.current_dungeon.peek_next_stage()
                if next_level is None:
                    logger.info("没有下一关，你胜利了，应该返回营地！！！！")
                else:
                    logger.info(
                        f"玩家输入 = {usr_input}, 进入下一关 = {next_level.name}"
                    )
                    # terminal_game.next_dungeon()
                    advance_to_next_stage(terminal_game)
                    await terminal_game.combat_pipeline.process()
            elif (
                terminal_game.current_combat_sequence.current_result
                == CombatResult.HERO_LOSE
            ):
                logger.info("英雄失败，应该返回营地！！！！")
            else:
                assert False, "不可能出现的情况！"
    else:
        logger.error(
            f"玩家输入 = {usr_input}, 目前不做任何处理，不在处理范围内！！！！！"
        )


###############################################################################################################################################
async def _process_home_state_input(terminal_game: TCGGame, usr_input: str) -> None:
    """处理家园状态下的玩家输入"""

    if usr_input == "/ad" or usr_input == "/advancing":
        await terminal_game.npc_home_pipeline.process()

    elif usr_input == "/ld" or usr_input == "/launch-dungeon":

        if len(terminal_game.current_dungeon.stages) == 0:
            logger.error(
                f"全部地下城已经结束。！！！！已经全部被清空！！！！或者不存在！！！！"
            )
            return

        logger.debug(f"玩家输入 = {usr_input}, 准备传送地下城")
        if not initialize_dungeon_first_entry(terminal_game):
            assert False, "传送地下城失败！"

        if len(terminal_game.current_combat_sequence.combats) == 0:
            logger.error(f"{usr_input} 没有战斗可以进行！！！！")
            return

        await terminal_game.combat_pipeline.process()

    elif "/hero" in usr_input or "/ho" in usr_input:
        # "/hero --params=角色.法师.奥露娜;角色.战士.卡恩"
        hero_command = _parse_hero_plan_command_input(usr_input)
        logger.debug(f"解析到的英雄命令: {hero_command}")
        _plan_action(terminal_game, hero_command["heroes"])
        await terminal_game.npc_home_pipeline.process()

    elif "/speak" in usr_input or "/ss" in usr_input:

        # 分析输入
        speak_command = _parse_speak_command_input(usr_input)

        # 处理输入
        if activate_speak_action(
            tcg_game=terminal_game,
            target=speak_command["target"],
            content=speak_command["content"],
        ):

            # player 执行一次, 这次基本是忽略推理标记的，所有NPC不推理。
            await terminal_game.player_home_pipeline.process()

            # 其他人执行一次。对应的NPC进行推理。
            # await terminal_game.home_state_pipeline.process()

    elif "/trans_home" in usr_input or "/th" in usr_input:
        # 分析输入
        home_trans_stage_command = _parse_home_trans_stage_command_input(usr_input)
        logger.info(f"解析到的家园传送命令: {home_trans_stage_command}")
        if _trans_stage_action(terminal_game, home_trans_stage_command["stage_name"]):
            # player 执行一次, 这次基本是忽略推理标记的，所有NPC不推理。
            await terminal_game.player_home_pipeline.process()

    else:
        logger.error(
            f"玩家输入 = {usr_input}, 目前不做任何处理，不在处理范围内！！！！！"
        )


###############################################################################################################################################
async def _process_player_input(terminal_game: TCGGame) -> None:

    player_actor_entity = terminal_game.get_player_entity()
    assert player_actor_entity is not None

    player_stage_entity = terminal_game.safe_get_stage_entity(player_actor_entity)
    assert player_stage_entity is not None

    # 其他状态下的玩家输入！！！！！！
    usr_input = input(
        f"[{terminal_game.player_session.name}/{player_stage_entity.name}/{player_actor_entity.name}]:"
    )
    usr_input = usr_input.strip().lower()

    # 处理输入
    if usr_input == "/q" or usr_input == "/quit":
        # 退出游戏
        logger.debug(
            f"玩家 主动 退出游戏 = {terminal_game.player_session.name}, {player_stage_entity.name}"
        )
        terminal_game.should_terminate = True
        return

    # 公用: 查看当前地下城系统
    if usr_input == "/vd" or usr_input == "/view-dungeon":
        logger.info(
            f"当前地下城系统 =\n{terminal_game.current_dungeon.model_dump_json(indent=4)}\n"
        )
        return

    # 公用：检查内网的llm服务的健康状态
    if usr_input == "/hc":
        await ChatClient.health_check()
        return

    # 根据游戏状态分发处理逻辑
    if terminal_game.is_player_in_dungeon:
        await _process_dungeon_state_input(terminal_game, usr_input)
    elif terminal_game.is_player_at_home:
        await _process_home_state_input(terminal_game, usr_input)
    else:
        logger.error(
            f"玩家输入 = {usr_input}, 目前不做任何处理，不在处理范围内！！！！！"
        )


###############################################################################################################################################
if __name__ == "__main__":

    # 初始化日志
    setup_logger()

    random_name = f"player-{datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}"
    fixed_name = "player-fixed"

    # 做一些设置
    user = random_name
    game = GLOBAL_TCG_GAME_NAME
    actor = create_actor_warrior().name

    # 运行游戏
    import asyncio

    asyncio.run(_run_game(user, game, actor))
