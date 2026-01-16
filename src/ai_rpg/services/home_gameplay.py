"""
家园游戏玩法服务模块

提供家园系统的核心API接口，处理玩家在家园状态下的各种游戏操作，
包括对话、场景切换、游戏推进和地下城传送等功能。
"""

from typing import Final
from fastapi import APIRouter, HTTPException, status
from loguru import logger
from ..game.tcg_game import TCGGame
from .game_server_dependencies import CurrentGameServer
from ..game.game_server import GameServer
from .home_actions import (
    activate_speak_action,
    activate_switch_stage,
    activate_plan_action,
)
from .dungeon_stage_transition import (
    initialize_dungeon_first_entry,
)
from ..models import (
    HomePlayerActionRequest,
    HomePlayerActionResponse,
    HomePlayerActionType,
    HomeAdvanceRequest,
    HomeAdvanceResponse,
    HomeTransDungeonRequest,
    HomeTransDungeonResponse,
)

###################################################################################################################################################################
home_gameplay_api_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
async def _validate_player_at_home(
    user_name: str,
    game_server: GameServer,
) -> TCGGame:
    """
    验证玩家是否在家园状态

    Args:
        user_name: 用户名
        game_server: 游戏服务器实例

    Returns:
        TCGGame: 验证通过的 TCG 游戏实例

    Raises:
        HTTPException(404): 房间或游戏实例不存在
        HTTPException(400): 玩家不在家园状态
    """

    # 检查房间是否存在
    if not game_server.has_room(user_name):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    # 获取房间实例并检查游戏是否存在
    current_room = game_server.get_room(user_name)
    assert current_room is not None, "_validate_player_at_home: room instance is None"
    if current_room._tcg_game is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有游戏，请先登录",
        )

    # 判断游戏状态，不是Home状态不可以推进。
    if not current_room._tcg_game.is_player_in_home_stage:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前不在家园状态，不能进行家园操作",
        )

    # 返回游戏实例
    return current_room._tcg_game


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@home_gameplay_api_router.post(
    path="/api/home/player_action/v1/", response_model=HomePlayerActionResponse
)
async def home_player_action(
    payload: HomePlayerActionRequest,
    game_server: CurrentGameServer,
) -> HomePlayerActionResponse:
    """
    家园玩家动作接口

    处理玩家在家园状态下的主动操作请求，包括对话和场景切换。

    Args:
        payload: 家园玩家动作请求对象
        game_server: 游戏服务器实例

    Returns:
        HomePlayerActionResponse: 包含会话消息列表的响应对象

    Raises:
        HTTPException(404): 玩家未登录或游戏实例不存在
        HTTPException(400): 玩家不在家园状态或动作激活失败
    """

    logger.info(f"/api/home/player_action/v1/: {payload.model_dump_json()}")

    # 验证前置条件并获取游戏实例
    rpg_game = await _validate_player_at_home(
        payload.user_name,
        game_server,
    )

    # 记录当前事件序列号，便于后续获取新增消息
    last_event_sequence: Final[int] = rpg_game.player_session.event_sequence

    # 根据动作类型激活对应的 Action 组件
    match payload.action:
        case HomePlayerActionType.SPEAK:
            # 激活对话动作：玩家与指定NPC进行对话交互
            success, error_detail = activate_speak_action(
                rpg_game,
                target=payload.arguments.get("target", ""),
                content=payload.arguments.get("content", ""),
            )

        case HomePlayerActionType.SWITCH_STAGE:
            # 激活场景切换动作：在家园内切换到不同的场景
            success, error_detail = activate_switch_stage(
                rpg_game, stage_name=payload.arguments.get("stage_name", "")
            )

        case _:
            # 未知的动作类型
            logger.error(f"未知的请求类型 = {payload.action}, 不能处理！")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"未知的请求类型 = {payload.action}, 不能处理！",
            )

    # 统一处理动作激活结果
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail,
        )

    # 执行玩家的 home pipeline 处理
    await rpg_game.player_home_pipeline.process()

    # 返回自上次事件序列号以来的新增消息
    return HomePlayerActionResponse(
        session_messages=rpg_game.player_session.get_messages_since(last_event_sequence)
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@home_gameplay_api_router.post(
    path="/api/home/advance/v1/", response_model=HomeAdvanceResponse
)
async def home_advance(
    payload: HomeAdvanceRequest,
    game_server: CurrentGameServer,
) -> HomeAdvanceResponse:
    """
    家园推进接口

    推进游戏流程，可选地激活指定角色的行动计划。

    Args:
        payload: 家园推进请求对象
        game_server: 游戏服务器实例

    Returns:
        HomeAdvanceResponse: 包含会话消息列表的响应对象

    Raises:
        HTTPException(404): 玩家未登录或游戏实例不存在
        HTTPException(400): 玩家不在家园状态或角色激活失败
    """

    logger.info(f"/api/home/advance/v1/: {payload.model_dump_json()}")

    # 验证前置条件并获取游戏实例
    rpg_game = await _validate_player_at_home(
        payload.user_name,
        game_server,
    )

    # 记录当前事件序列号，便于后续获取新增消息
    last_event_sequence: Final[int] = rpg_game.player_session.event_sequence

    # 如果指定了actors，先为这些角色激活行动计划
    if payload.actors:
        success, error_detail = activate_plan_action(rpg_game, payload.actors)
        if not success:
            # 行动计划激活失败，抛出包含具体错误信息的异常
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_detail,
            )

    # 推进游戏流程：执行NPC的home pipeline，自动推进游戏状态
    await rpg_game.npc_home_pipeline.process()

    # 返回自上次事件序列号以来的新增消息
    return HomeAdvanceResponse(
        session_messages=rpg_game.player_session.get_messages_since(last_event_sequence)
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@home_gameplay_api_router.post(
    path="/api/home/trans_dungeon/v1/", response_model=HomeTransDungeonResponse
)
async def home_trans_dungeon(
    payload: HomeTransDungeonRequest,
    game_server: CurrentGameServer,
) -> HomeTransDungeonResponse:
    """
    家园传送地下城接口

    处理玩家从家园进入地下城的传送请求。

    Args:
        payload: 家园传送地下城请求对象
        game_server: 游戏服务器实例

    Returns:
        HomeTransDungeonResponse: 包含请求信息的响应对象

    Raises:
        HTTPException(404): 玩家未登录或没有可用的地下城
        HTTPException(400): 玩家不在家园状态
        HTTPException(500): 地下城初始化失败
    """

    logger.info(f"/api/home/trans_dungeon/v1/: user={payload.user_name}")

    # 验证前置条件并获取游戏实例
    rpg_game = await _validate_player_at_home(
        payload.user_name,
        game_server,
    )

    # 检查地下城是否存在可用的关卡
    if len(rpg_game.current_dungeon.stages) == 0:
        logger.warning(
            f"玩家 {payload.user_name} 尝试传送地下城失败: 当前地下城没有可用关卡"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="当前没有可用的地下城关卡",
        )

    # 执行地下城首次进入初始化
    # 初始化包括设置玩家状态、加载地下城场景、准备战斗环境等
    if not initialize_dungeon_first_entry(rpg_game, rpg_game.current_dungeon):
        logger.error(f"玩家 {payload.user_name} 地下城初始化失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="地下城初始化失败",
        )

    # 返回传送成功响应
    return HomeTransDungeonResponse(
        message=payload.model_dump_json(),
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
