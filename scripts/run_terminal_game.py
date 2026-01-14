"""终端集成测试工具 - Client/Server 一体化开发环境。

本脚本用于开发和测试游戏业务逻辑，将客户端和服务器端合并在一起运行。
通过终端命令行交互来模拟客户端输入，直接调用服务器端的正式业务代码（ai_rpg.services），
实现快速的业务逻辑开发、调试和验证。

架构说明：
    - Client/Server 融合：在单进程中同时运行客户端交互和服务器逻辑
    - 真实业务代码：调用 ai_rpg.services 中的正式服务器业务逻辑
    - 终端交互：通过命令行输入模拟客户端操作，方便调试

主要用途：
    - 开发新的游戏功能和业务逻辑
    - 测试服务器端的游戏流程和状态管理
    - 快速验证 NPC 对话、战斗系统、场景切换等功能
    - 无需启动完整的网络服务即可测试游戏逻辑

使用方法：
    python scripts/run_terminal_game.py
"""

import os
import sys

# 将 src 目录添加到模块搜索路径
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

from typing import Dict
from loguru import logger
from ai_rpg.chat_services.client import ChatClient
from ai_rpg.configuration import (
    server_configuration,
)
from ai_rpg.utils import parse_command_args
from ai_rpg.game.config import GLOBAL_TCG_GAME_NAME, setup_logger
from ai_rpg.demo import (
    create_training_dungeon,
    create_single_hunter_blueprint,
)
from ai_rpg.game.player_session import PlayerSession
from ai_rpg.game.tcg_game import (
    TCGGame,
)
from ai_rpg.game.world_persistence import (
    get_user_world_data,
    delete_user_world_data,
)
from ai_rpg.models import (
    World,
)
from ai_rpg.services.home_actions import (
    activate_speak_action,
    activate_switch_stage,
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


###############################################################################################################################################
async def _run_game(
    user: str,
    game: str,
) -> None:
    """游戏主循环入口。

    初始化游戏环境，创建或加载游戏世界，并进入主循环处理玩家输入。
    游戏循环会持续运行直到玩家退出或游戏终止信号触发。

    Args:
        user: 玩家用户名，用于标识玩家身份和存档
        game: 游戏名称，用于区分不同的游戏实例

    工作流程：
        1. 删除旧存档（测试模式）
        2. 创建新的游戏世界和玩家角色
        3. 初始化聊天服务和游戏系统
        4. 进入主循环处理玩家回合
        5. 游戏结束后保存并清理资源

    Note:
        当前为测试模式，不允许加载已有存档
    """

    # 注意，如果确定player是固定的，但是希望每次玩新游戏，就调用这句。
    # 或者，换成random_name，随机生成一个player名字。
    delete_user_world_data(user, GLOBAL_TCG_GAME_NAME)

    # 先检查一下world_data是否存在
    world_data = get_user_world_data(user, game)

    # 判断是否存在world数据
    if world_data is None:

        # 获取world_blueprint
        world_blueprint = create_single_hunter_blueprint(game)
        assert world_blueprint is not None, "world blueprint 反序列化失败"

        # 如果world不存在，说明是第一次创建游戏
        world_data = World(
            runtime_index=1000,
            entities_serialization=[],
            agents_context={},
            dungeon=create_training_dungeon(),
            blueprint=world_blueprint,
        )

    else:
        assert False, "测试阶段，不允许加载存档的游戏数据！"

    # 依赖注入，创建新的游戏
    assert world_data is not None, "World data must exist to create a game"
    terminal_game = TCGGame(
        name=game,
        player_session=PlayerSession(
            name=user,
            actor=world_data.blueprint.player_actor,
            game=game,
        ),
        world=world_data,
    )

    # 初始化聊天客户端
    ChatClient.initialize_url_config(server_configuration)

    # 启动游戏的判断，是第一次建立还是恢复？
    if len(terminal_game.world.entities_serialization) == 0:
        logger.info(f"游戏中没有实体 = {game}, 说明是第一次创建游戏")
        # 直接构建ecs
        terminal_game.new_game().save_game()

    else:
        logger.warning(f"游戏中有实体 = {game}，需要通过数据恢复实体，是游戏回复的过程")
        # 测试！回复ecs
        terminal_game.load_game().save_game()

    # 初始化！
    await terminal_game.initialize()

    # 主循环
    while True:

        # 处理玩家回合
        await _handle_player_turn(terminal_game)

        # 检查是否需要终止游戏
        if terminal_game.should_terminate:
            logger.info(f"游戏终止信号收到，准备退出游戏 = {user}, {game}")
            break

    # 保存游戏并退出
    terminal_game.save_game()
    terminal_game.exit()


###############################################################################################################################################
async def _process_dungeon(terminal_game: TCGGame, usr_input: str) -> None:
    """
    处理地下城状态下的玩家输入。

    Args:
        terminal_game: 游戏实例
        usr_input: 用户输入的命令字符串（已经过 strip 和 lower 处理）

    支持的命令：
        /dc - 抗牌，只能在战斗中使用
        /pc - 打牌，只能在战斗中使用
        /trans_home - 返回家园，只能在战斗结束后使用
        /advance_next_dungeon - 进入下一关，只能在战斗胜利后使用
    """

    if usr_input == "/dc":

        if not terminal_game.current_combat_sequence.is_ongoing:
            logger.error(f"{usr_input} 只能在战斗中使用is_on_going_phase")
            return

        logger.debug(f"玩家输入 = {usr_input}, 准备抽卡")
        activate_actor_card_draws(terminal_game)

        await terminal_game.combat_pipeline.process()

    elif usr_input == "/pc":

        if not terminal_game.current_combat_sequence.is_ongoing:
            logger.error(f"{usr_input} 只能在战斗中使用is_on_going_phase")
            return

        # 执行打牌行动(现在使用随机选行动)
        success, message = activate_random_play_cards(terminal_game)
        if success:
            await terminal_game.combat_pipeline.process()
        else:
            logger.error(f"打牌失败: {message}")

    elif usr_input == "/trans_home":

        if (
            len(terminal_game.current_combat_sequence.combats) == 0
            or not terminal_game.current_combat_sequence.is_post_combat
        ):
            logger.error(f"{usr_input} 只能在战斗后使用!!!!!")
            return

        logger.debug(f"玩家输入 = {usr_input}, 准备传送回家")
        complete_dungeon_and_return_home(terminal_game)

    elif usr_input == "/advance_next_dungeon":

        if not terminal_game.current_combat_sequence.is_post_combat:
            logger.error(f"{usr_input} 只能在战斗后使用")
            return

        if terminal_game.current_combat_sequence.is_lost:
            logger.info("英雄失败，应该返回营地！！！！")
            return

        if not terminal_game.current_combat_sequence.is_won:
            assert False, "不可能出现的情况！"

        next_level = terminal_game.current_dungeon.peek_next_stage()
        if next_level is None:
            logger.info("没有下一关，你胜利了，应该返回营地！！！！")
            return

        logger.info(f"玩家输入 = {usr_input}, 进入下一关 = {next_level.name}")
        advance_to_next_stage(terminal_game, terminal_game.current_dungeon)
        await terminal_game.combat_pipeline.process()

    else:
        logger.error(
            f"玩家输入 = {usr_input}, 目前不做任何处理，不在处理范围内！！！！！"
        )


###############################################################################################################################################
async def _process_home(terminal_game: TCGGame, usr_input: str) -> None:
    """
    处理家园状态下的玩家输入。

    Args:
        terminal_game: 游戏实例
        usr_input: 用户输入的命令字符串（已经过 strip 和 lower 处理）

    支持的命令：
        /ad - 推进 NPC 行动
        /ld - 启动地下城
        /speak --target=<角色> --content=<内容> - 与 NPC 对话
        /switch_stage --stage=<场景名> - 切换场景
    """

    if usr_input == "/ad":
        await terminal_game.npc_home_pipeline.process()

    elif usr_input == "/ld":

        if len(terminal_game.current_dungeon.stages) == 0:
            logger.error(
                f"全部地下城已经结束。！！！！已经全部被清空！！！！或者不存在！！！！"
            )
            return

        logger.debug(f"玩家输入 = {usr_input}, 准备传送地下城")
        if not initialize_dungeon_first_entry(
            terminal_game, terminal_game.current_dungeon
        ):
            assert False, "传送地下城失败！"

        if len(terminal_game.current_combat_sequence.combats) == 0:
            logger.error(f"{usr_input} 没有战斗可以进行！！！！")
            return

        await terminal_game.combat_pipeline.process()

    elif usr_input.startswith("/speak"):

        # 分析输入
        parsed_speak_command = _parse_speak(usr_input)

        # 添加说话行动
        success, _ = activate_speak_action(
            tcg_game=terminal_game,
            target=parsed_speak_command.get("target", ""),
            content=parsed_speak_command.get("content", ""),
        )

        if success:
            # player 执行一次, 这次基本是忽略推理标记的，所有NPC不推理。
            await terminal_game.player_home_pipeline.process()

    elif usr_input.startswith("/switch_stage"):
        # 分析输入
        parsed_switch_stage_command = _parse_switch_stage(usr_input)

        # 添加场景转换行动
        success, _ = activate_switch_stage(
            tcg_game=terminal_game,
            stage_name=parsed_switch_stage_command.get("stage", ""),
        )
        if success:
            # player 执行一次, 这次基本是忽略推理标记的，所有NPC不推理。
            await terminal_game.player_home_pipeline.process()

    else:
        logger.error(
            f"玩家输入 = {usr_input}, 目前不做任何处理，不在处理范围内！！！！！"
        )


###############################################################################################################################################
async def _handle_player_turn(terminal_game: TCGGame) -> None:
    """
    处理玩家的一个回合。

    读取玩家输入，处理通用命令，并根据玩家当前所在状态分发到相应的处理器。

    Args:
        terminal_game: 游戏实例

    通用命令：
        /q - 退出游戏
        /vd - 查看当前地下城系统
        /hc - 检查 LLM 服务健康状态

    Note:
        根据玩家所在状态（地下城/家园）分发到 _process_dungeon 或 _process_home
    """

    player_actor_entity = terminal_game.get_player_entity()
    assert player_actor_entity is not None

    player_stage_entity = terminal_game.resolve_stage_entity(player_actor_entity)
    assert player_stage_entity is not None

    # 其他状态下的玩家输入！！！！！！
    usr_input = input(
        f"[{terminal_game.player_session.name}/{player_stage_entity.name}/{player_actor_entity.name}]:"
    )
    usr_input = usr_input.strip().lower()

    # 处理输入
    if usr_input == "/q":
        # 退出游戏
        logger.debug(
            f"玩家 主动 退出游戏 = {terminal_game.player_session.name}, {player_stage_entity.name}"
        )
        terminal_game.should_terminate = True
        return

    # 公用: 查看当前地下城系统
    if usr_input == "/vd":
        logger.info(
            f"当前地下城系统 =\n{terminal_game.current_dungeon.model_dump_json(indent=4)}\n"
        )
        return

    # 公用：检查内网的llm服务的健康状态
    if usr_input == "/hc":
        await ChatClient.health_check()
        return

    # 根据游戏状态分发处理逻辑
    if terminal_game.is_player_in_dungeon_stage:
        await _process_dungeon(terminal_game, usr_input)
    elif terminal_game.is_player_in_home_stage:
        await _process_home(terminal_game, usr_input)
    else:
        logger.error(
            f"玩家输入 = {usr_input}, 目前不做任何处理，不在处理范围内！！！！！"
        )


############################################################################################################
def _parse_speak(usr_input: str) -> Dict[str, str]:
    """
    解析用户输入的说话命令，提取目标角色和说话内容。

    Args:
        usr_input: 用户输入的命令字符串

    Returns:
        包含 target 和 content 字段的字典，如果不是 /speak 命令则返回空字典

    Examples:
        >>> _parse_speak("/speak --target=角色.法师.奥露娜 --content=我还是需要准备一下")
        {'target': '角色.法师.奥露娜', 'content': '我还是需要准备一下'}

        >>> _parse_speak("/speak --target=玩家 --content=你好")
        {'target': '玩家', 'content': '你好'}
    """
    if not usr_input.startswith("/speak"):
        return {}

    return parse_command_args(usr_input, {"target", "content"})


############################################################################################################
def _parse_switch_stage(usr_input: str) -> Dict[str, str]:
    """
    解析用户输入的场景切换命令，提取目标场景名称。

    Args:
        usr_input: 用户输入的命令字符串

    Returns:
        包含 stage 字段的字典，如果不是 /switch_stage 命令则返回空字典

    Examples:
        >>> _parse_switch_stage("/switch_stage --stage=场景.营地")
        {'stage': '场景.营地'}

        >>> _parse_switch_stage("/switch_stage --stage=场景.训练场")
        {'stage': '场景.训练场'}
    """
    if not usr_input.startswith("/switch_stage"):
        return {}

    return parse_command_args(usr_input, {"stage"})


###############################################################################################################################################
if __name__ == "__main__":

    # 初始化日志
    setup_logger()

    # 随机用户名，这样每次运行都是新的存档
    random_user_name = (
        f"terminal-player-{datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}"
    )

    # 运行游戏
    import asyncio

    asyncio.run(_run_game(random_user_name, GLOBAL_TCG_GAME_NAME))
