"""
家园游戏玩法服务模块

提供家园系统的核心API接口，处理玩家在家园状态下的各种游戏操作，
包括对话、场景切换、游戏推进和地下城传送等功能。
"""

import asyncio
from datetime import datetime
from fastapi import APIRouter, HTTPException, status
from loguru import logger
from ..game.tcg_game import TCGGame
from .game_server_dependencies import CurrentGameServer
from ..game.game_server import GameServer
from .home_actions import (
    activate_speak_action,
    activate_switch_stage,
    activate_stage_plan,
    activate_generate_dungeon,
)
from .dungeon_lifecycle import (
    setup_dungeon,
    enter_dungeon_first_stage,
)
from ..models import (
    HomePlayerActionRequest,
    HomePlayerActionResponse,
    HomePlayerActionType,
    HomeAdvanceRequest,
    HomeAdvanceResponse,
    HomeEnterDungeonRequest,
    HomeEnterDungeonResponse,
    HomeGenerateDungeonRequest,
    HomeGenerateDungeonResponse,
    TaskStatus,
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

    # 获取房间并用每玩家锁避免并发状态竞争
    current_room = game_server.get_room(payload.user_name)
    if current_room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    async with current_room._lock:

        # 验证前置条件并获取游戏实例
        rpg_game = await _validate_player_at_home(
            payload.user_name,
            game_server,
        )

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

    # 创建 home pipeline 后台任务（在锁外创建，让任务在后台独立持锁执行）
    home_action_task = game_server.create_task()

    asyncio.create_task(
        _execute_home_pipeline_task(
            home_action_task.task_id,
            payload.user_name,
            game_server,
        )
    )

    logger.info(
        f"📝 创建 home pipeline 任务: task_id={home_action_task.task_id}, user={payload.user_name}"
    )

    return HomePlayerActionResponse(
        task_id=home_action_task.task_id,
        status=TaskStatus.RUNNING.value,
        message="home pipeline 任务已启动，请通过会话消息查询结果",
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

    # 获取房间并用每玩家锁避免并发状态竞争
    current_room = game_server.get_room(payload.user_name)
    if current_room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    async with current_room._lock:
        # 验证前置条件并获取游戏实例
        rpg_game = await _validate_player_at_home(
            payload.user_name,
            game_server,
        )

        # 根据请求参数选择性激活指定角色的行动计划
        success, error_detail = activate_stage_plan(rpg_game)
        if not success:
            # 行动计划激活失败，抛出包含具体错误信息的异常
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_detail,
            )

    # 创建 home pipeline 后台任务（在锁外创建，让任务在后台独立持锁执行）
    home_advance_task = game_server.create_task()

    asyncio.create_task(
        _execute_home_pipeline_task(
            home_advance_task.task_id,
            payload.user_name,
            game_server,
        )
    )

    return HomeAdvanceResponse(
        task_id=home_advance_task.task_id,
        status=TaskStatus.RUNNING.value,
        message="home pipeline 任务已启动，请通过会话消息查询结果",
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@home_gameplay_api_router.post(
    path="/api/home/enter_dungeon/v1/", response_model=HomeEnterDungeonResponse
)
async def home_enter_dungeon(
    payload: HomeEnterDungeonRequest,
    game_server: CurrentGameServer,
) -> HomeEnterDungeonResponse:
    """
    家园传送地下城接口

    处理玩家从家园进入地下城的传送请求。

    Args:
        payload: 家园传送地下城请求对象
        game_server: 游戏服务器实例

    Returns:
        HomeEnterDungeonResponse: 包含请求信息的响应对象

    Raises:
        HTTPException(404): 玩家未登录或没有可用的地下城
        HTTPException(400): 玩家不在家园状态
        HTTPException(500): 地下城初始化失败
    """

    logger.info(f"/api/home/enter_dungeon/v1/: user={payload.user_name}")

    # 获取房间并用每玩家锁避免并发状态竞争
    current_room = game_server.get_room(payload.user_name)
    if current_room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    async with current_room._lock:
        # 验证前置条件并获取游戏实例
        rpg_game = await _validate_player_at_home(
            payload.user_name,
            game_server,
        )

        # 检查地下城是否存在可用的关卡
        # if len(rpg_game.current_dungeon.rooms) == 0:
        #     logger.warning(
        #         f"玩家 {payload.user_name} 尝试传送地下城失败: 当前地下城没有可用关卡"
        #     )
        #     raise HTTPException(
        #         status_code=status.HTTP_404_NOT_FOUND,
        #         detail="当前没有可用的地下城关卡",
        #     )

        # 第一步：创建地下城实体（幂等）
        success, error_detail = setup_dungeon(rpg_game, rpg_game.current_dungeon)
        if not success:
            logger.error(f"玩家 {payload.user_name} 地下城实体创建失败: {error_detail}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="地下城实体创建失败",
            )

        # 第二步：组建远征队并进入第一关
        success, error_detail = enter_dungeon_first_stage(
            rpg_game, rpg_game.current_dungeon
        )
        if not success:
            logger.error(f"玩家 {payload.user_name} 进入地下城失败: {error_detail}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="进入地下城失败",
            )

        # 返回传送成功响应
        return HomeEnterDungeonResponse(
            message=payload.model_dump_json(),
        )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@home_gameplay_api_router.post(
    path="/api/home/generate_dungeon/v1/", response_model=HomeGenerateDungeonResponse
)
async def home_generate_dungeon(
    payload: HomeGenerateDungeonRequest,
    game_server: CurrentGameServer,
) -> HomeGenerateDungeonResponse:
    """
    家园生成地下城接口

    在家园状态下触发地下城文本与图片的生成流程（dungeon_setup_pipeline）。
    添加 GenerateDungeonAction 到玩家实体，后台异步执行 Steps 1-4 文本生成及图片生成。

    Args:
        payload: 家园生成地下城请求对象
        game_server: 游戏服务器实例

    Returns:
        HomeGenerateDungeonResponse: 包含后台任务 ID 的响应对象

    Raises:
        HTTPException(404): 玩家未登录或游戏实例不存在
        HTTPException(400): 玩家不在家园状态或动作激活失败
    """

    logger.info(f"/api/home/generate_dungeon/v1/: user={payload.user_name}")

    # 获取房间并用每玩家锁避免并发状态竞争
    current_room = game_server.get_room(payload.user_name)
    if current_room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    async with current_room._lock:
        # 验证前置条件并获取游戏实例
        rpg_game = await _validate_player_at_home(
            payload.user_name,
            game_server,
        )

        # 激活地下城生成动作
        success, error_detail = activate_generate_dungeon(rpg_game)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_detail,
            )

    # 创建 dungeon setup pipeline 后台任务（在锁外创建，让任务在后台独立持锁执行）
    generate_dungeon_task = game_server.create_task()

    asyncio.create_task(
        _execute_dungeon_setup_pipeline_task(
            generate_dungeon_task.task_id,
            payload.user_name,
            game_server,
        )
    )

    logger.info(
        f"📝 创建 dungeon setup pipeline 任务: task_id={generate_dungeon_task.task_id}, user={payload.user_name}"
    )

    return HomeGenerateDungeonResponse(
        task_id=generate_dungeon_task.task_id,
        status=TaskStatus.RUNNING.value,
        message="dungeon setup pipeline 任务已启动，请通过会话消息查询结果",
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
async def _execute_dungeon_setup_pipeline_task(
    task_id: str,
    user_name: str,
    game_server: GameServer,
) -> None:
    """后台执行 dungeon setup pipeline 任务

    在后台异步执行 dungeon_setup_pipeline 并更新任务状态。
    使用房间锁保证同一玩家不会并发执行。

    Args:
        task_id: 任务唯一标识符
        user_name: 用户名
        game_server: 游戏服务器实例
    """
    try:
        logger.info(
            f"🚀 dungeon setup pipeline 任务开始: task_id={task_id}, user={user_name}"
        )

        current_room = game_server.get_room(user_name)
        if current_room is None:
            raise ValueError(f"游戏实例不存在: user={user_name}")

        async with current_room._lock:
            rpg_game = await _validate_player_at_home(user_name, game_server)
            await rpg_game._dungeon_setup_pipeline.process()

        task_record = game_server.get_task(task_id)
        if task_record is not None:
            task_record.status = TaskStatus.COMPLETED
            task_record.end_time = datetime.now().isoformat()

        logger.info(
            f"✅ dungeon setup pipeline 任务完成: task_id={task_id}, user={user_name}"
        )

    except Exception as e:
        logger.error(
            f"❌ dungeon setup pipeline 任务失败: task_id={task_id}, user={user_name}, error={e}"
        )
        task_record = game_server.get_task(task_id)
        if task_record is not None:
            task_record.status = TaskStatus.FAILED
            task_record.error = str(e)
            task_record.end_time = datetime.now().isoformat()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
async def _execute_home_pipeline_task(
    task_id: str,
    user_name: str,
    game_server: GameServer,
) -> None:
    """后台执行 home pipeline 任务

    在后台异步执行 home pipeline 并更新任务状态。
    使用房间锁保证同一玩家不会并发执行。

    Args:
        task_id: 任务唯一标识符
        user_name: 用户名
        game_server: 游戏服务器实例
    """
    try:
        logger.info(f"🚀 home pipeline 任务开始: task_id={task_id}, user={user_name}")

        current_room = game_server.get_room(user_name)
        if current_room is None:
            raise ValueError(f"游戏实例不存在: user={user_name}")

        async with current_room._lock:
            rpg_game = await _validate_player_at_home(user_name, game_server)
            await rpg_game._home_pipeline.process()

        task_record = game_server.get_task(task_id)
        if task_record is not None:
            task_record.status = TaskStatus.COMPLETED
            task_record.end_time = datetime.now().isoformat()

        logger.info(f"✅ home pipeline 任务完成: task_id={task_id}, user={user_name}")

    except Exception as e:
        logger.error(
            f"❌ home pipeline 任务失败: task_id={task_id}, user={user_name}, error={e}"
        )
        task_record = game_server.get_task(task_id)
        if task_record is not None:
            task_record.status = TaskStatus.FAILED
            task_record.error = str(e)
            task_record.end_time = datetime.now().isoformat()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
