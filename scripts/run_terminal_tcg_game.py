import os
from pathlib import Path
import sys

# 将 src 目录添加到模块搜索路径
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

from typing import Dict, Set, TypedDict, cast
from loguru import logger

# from multi_agents_game.chat_services.manager import (
#     ChatClientManager,
#     ChatApiEndpointOptions,
# )
from multi_agents_game.chat_services.client import ChatClient
from multi_agents_game.settings import (
    initialize_server_settings_instance,
)
from multi_agents_game.game.game_config import GLOBAL_GAME_NAME, setup_logger
from multi_agents_game.demo import (
    create_actor_warrior,
    create_demo_dungeon5,
)
from multi_agents_game.game.player_client import PlayerClient
from multi_agents_game.game.tcg_game import TCGGameState
from multi_agents_game.game.terminal_tcg_game import (
    TerminalTCGGame,
    TerminalGameUserOptions,
)
from multi_agents_game.models import CombatResult, World


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
async def _run_game(
    terminal_game_user_options: TerminalGameUserOptions,
) -> None:

    # 注意，如果确定player是固定的，但是希望每次玩新游戏，就调用这句。
    # 或者，换成random_name，随机生成一个player名字。
    terminal_game_user_options.delete_world_data()

    # 先检查一下world_data是否存在
    world_exists = terminal_game_user_options.world_data

    #
    if world_exists is None:

        # 获取world_boot_data
        world_boot = terminal_game_user_options.world_boot_data
        assert world_boot is not None, "WorldBootDocument 反序列化失败"

        # 如果world不存在，说明是第一次创建游戏
        world_exists = World(boot=world_boot)

        # 运行时生成地下城系统
        world_exists.dungeon = create_demo_dungeon5()

    else:
        logger.info(
            f"恢复游戏: {terminal_game_user_options.user}, {terminal_game_user_options.game}"
        )

    ### 创建一些子系统。!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    server_settings = initialize_server_settings_instance(Path("server_settings.json"))

    # 依赖注入，创建新的游戏
    assert world_exists is not None, "World data must exist to create a game"
    terminal_game = TerminalTCGGame(
        name=terminal_game_user_options.game,
        player=PlayerClient(
            name=terminal_game_user_options.user,
            actor=terminal_game_user_options.actor,
        ),
        world=world_exists,
        # chat_client_manager=ChatClientManager(
        #     azure_openai_base_localhost_urls=server_settings.azure_openai_base_localhost_urls,
        #     azure_openai_chat_localhost_urls=server_settings.azure_openai_chat_localhost_urls,
        #     deepseek_base_localhost_urls=server_settings.deepseek_base_localhost_urls,
        #     deepseek_chat_localhost_urls=server_settings.deepseek_chat_localhost_urls,
        #     deepseek_rag_chat_localhost_urls=server_settings.deepseek_rag_chat_localhost_urls,
        #     deepseek_undefined_chat_localhost_urls=server_settings.deepseek_undefined_chat_localhost_urls,
        #     deepseek_mcp_chat_localhost_urls=server_settings.deepseek_mcp_chat_localhost_urls,
        # ),
    )

    ChatClient.initialize_url_config(server_settings)

    # 启动游戏的判断，是第一次建立还是恢复？
    if len(terminal_game.world.entities_snapshot) == 0:
        logger.warning(
            f"游戏中没有实体 = {terminal_game_user_options.game}, 说明是第一次创建游戏"
        )
        # 直接构建ecs
        terminal_game.new_game().save()

    else:
        logger.warning(
            f"游戏中有实体 = {terminal_game_user_options.game}，需要通过数据恢复实体，是游戏回复的过程"
        )
        # 测试！回复ecs
        terminal_game.load_game().save()

    # 测试一下玩家控制角色，如果没有就是错误。
    player_entity = terminal_game.get_player_entity()
    assert player_entity is not None
    if player_entity is None:
        logger.error(
            f"玩家实体不存在 = {terminal_game_user_options.user}, {terminal_game_user_options.game}, {terminal_game_user_options.actor}"
        )
        exit(1)

    # 游戏循环。。。。。。
    while True:

        await _process_player_input(terminal_game)
        if terminal_game.will_exit:
            break

    # 会保存一下。
    terminal_game.save()
    # 退出游戏
    terminal_game.exit()
    # 退出
    exit(0)


###############################################################################################################################################
async def _process_dungeon_state_input(
    terminal_game: TerminalTCGGame, usr_input: str
) -> None:
    """处理地下城状态下的玩家输入"""

    if usr_input == "/dc" or usr_input == "/draw-cards":

        if not terminal_game.current_engagement.is_on_going_phase:
            logger.error(f"{usr_input} 只能在战斗中使用is_on_going_phase")
            return

        logger.debug(f"玩家输入 = {usr_input}, 准备抽卡")
        terminal_game.activate_draw_cards_action()

        await terminal_game.dungeon_combat_pipeline.process()

    elif usr_input == "/pc" or "/play-cards" in usr_input:

        if not terminal_game.current_engagement.is_on_going_phase:
            logger.error(f"{usr_input} 只能在战斗中使用is_on_going_phase")
            return

        # 统一解析卡牌命令（/pc 和 /play-cards 都用同样的逻辑处理）
        player_cards_command = _parse_play_cards_command_input(usr_input)
        logger.debug(
            f"玩家输入 = {usr_input}, 解析到的卡牌命令: {player_cards_command}"
        )

        # 传入解析到的卡牌参数，如果没有参数则传入None
        skill_options = (
            player_cards_command["params"] if player_cards_command["params"] else None
        )
        if terminal_game.activate_play_cards_action(skill_options):
            await terminal_game.dungeon_combat_pipeline.process()

    elif usr_input == "/rth" or usr_input == "/return-to-home":

        if (
            len(terminal_game.current_engagement.combats) == 0
            or not terminal_game.current_engagement.is_post_wait_phase
        ):
            logger.error(f"{usr_input} 只能在战斗后使用!!!!!")
            return

        logger.debug(f"玩家输入 = {usr_input}, 准备传送回家")
        terminal_game.return_home()

    elif usr_input == "/and" or usr_input == "/advance-next-dungeon":

        if terminal_game.current_engagement.is_post_wait_phase:
            if terminal_game.current_engagement.combat_result == CombatResult.HERO_WIN:

                next_level = terminal_game.current_dungeon.next_level()
                if next_level is None:
                    logger.info("没有下一关，你胜利了，应该返回营地！！！！")
                else:
                    logger.info(
                        f"玩家输入 = {usr_input}, 进入下一关 = {next_level.name}"
                    )
                    terminal_game.next_dungeon()
                    await terminal_game.dungeon_combat_pipeline.process()
            elif (
                terminal_game.current_engagement.combat_result == CombatResult.HERO_LOSE
            ):
                logger.info("英雄失败，应该返回营地！！！！")
            else:
                assert False, "不可能出现的情况！"
    else:
        logger.error(
            f"玩家输入 = {usr_input}, 目前不做任何处理，不在处理范围内！！！！！"
        )


###############################################################################################################################################
async def _process_home_state_input(
    terminal_game: TerminalTCGGame, usr_input: str
) -> None:
    """处理家园状态下的玩家输入"""

    if usr_input == "/ad" or usr_input == "/advancing":
        await terminal_game.home_state_pipeline.process()

    elif usr_input == "/ld" or usr_input == "/launch-dungeon":

        if len(terminal_game.current_dungeon.levels) == 0:
            logger.error(
                f"全部地下城已经结束。！！！！已经全部被清空！！！！或者不存在！！！！"
            )
            return

        logger.debug(f"玩家输入 = {usr_input}, 准备传送地下城")
        if not terminal_game.launch_dungeon():
            assert False, "传送地下城失败！"

        if len(terminal_game.current_engagement.combats) == 0:
            logger.error(f"{usr_input} 没有战斗可以进行！！！！")
            return

        # if not terminal_game.current_engagement.combat_phase:
        #     logger.error(f"{usr_input} 错误，未进入战斗！！！")
        #     return

        # await _execute_terminal_game(terminal_game)
        await terminal_game.dungeon_combat_pipeline.process()

    elif "/speak" in usr_input or "/ss" in usr_input:

        # 分析输入
        speak_command = _parse_speak_command_input(usr_input)

        # 处理输入
        if terminal_game.activate_speak_action(
            target=speak_command["target"],
            content=speak_command["content"],
        ):

            # player 执行一次, 这次基本是忽略推理标记的，所有NPC不推理。
            await terminal_game.home_state_pipeline.process()

            # 其他人执行一次。对应的NPC进行推理。
            await terminal_game.home_state_pipeline.process()

    else:
        logger.error(
            f"玩家输入 = {usr_input}, 目前不做任何处理，不在处理范围内！！！！！"
        )


###############################################################################################################################################
async def _process_player_input(terminal_game: TerminalTCGGame) -> None:

    player_actor_entity = terminal_game.get_player_entity()
    assert player_actor_entity is not None

    player_stage_entity = terminal_game.safe_get_stage_entity(player_actor_entity)
    assert player_stage_entity is not None

    # 其他状态下的玩家输入！！！！！！
    usr_input = input(
        f"[{terminal_game.player.name}/{player_stage_entity._name}/{player_actor_entity._name}]:"
    )
    usr_input = usr_input.strip().lower()

    # 处理输入
    if usr_input == "/q" or usr_input == "/quit":
        # 退出游戏
        logger.debug(
            f"玩家 主动 退出游戏 = {terminal_game.player.name}, {player_stage_entity._name}"
        )
        terminal_game.will_exit = True
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

    # 公用：检查内网的llm服务的健康状态
    # if usr_input == "/azure_openai":
    #     await terminal_game.chat_client_manager.health_check(
    #         ChatApiEndpointOptions.AZURE_OPENAI_BASE
    #     )
    #     return

    # 根据游戏状态分发处理逻辑
    if terminal_game.current_game_state == TCGGameState.DUNGEON:
        await _process_dungeon_state_input(terminal_game, usr_input)
    elif terminal_game.current_game_state == TCGGameState.HOME:
        await _process_home_state_input(terminal_game, usr_input)
    else:
        logger.error(
            f"玩家输入 = {usr_input}, 目前不做任何处理，不在处理范围内！！！！！"
        )


###############################################################################################################################################
if __name__ == "__main__":

    # player_cards_command = _parse_play_cards_command_input("/play-cards --params=火球术=敌人.哥布林;治疗术=自己")

    # 初始化日志
    setup_logger()
    import datetime

    random_name = f"player-{datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}"
    fixed_name = "player-fixed"

    # 做一些设置
    terminal_user_session_options = TerminalGameUserOptions(
        user=random_name,
        game=GLOBAL_GAME_NAME,
        actor=create_actor_warrior().name,
    )

    # 运行游戏
    import asyncio

    asyncio.run(_run_game(terminal_user_session_options))
