"""
家园游戏玩法服务模块

提供家园系统的核心API接口，处理玩家在家园状态下的各种游戏操作，
包括对话、场景切换、游戏推进和地下城传送等功能。
"""

import asyncio
from fastapi import APIRouter, HTTPException, status
from loguru import logger
from .game_server_dependencies import CurrentGameServer
from .home_tasks import (
    _validate_player_at_home,
    _execute_home_pipeline_task,
    _execute_dungeon_generate_pipeline_task,
)
from .home_actions import (
    activate_speak_action,
    activate_switch_stage,
    activate_equip_item,
    activate_stage_plan,
    activate_generate_dungeon,
    activate_craft_item,
    add_party_member,
    remove_party_member,
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
    HomeRosterAddRequest,
    HomeRosterAddResponse,
    HomeRosterRemoveRequest,
    HomeRosterRemoveResponse,
    HomeCraftItemRequest,
    HomeCraftItemResponse,
    TaskStatus,
)

###################################################################################################################################################################
home_gameplay_api_router = APIRouter()


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

            case HomePlayerActionType.EQUIP_ITEM:
                # 激活装备动作：将背包中指定物品装备到对应槽位
                # 键缺失 → None（不更换）；值为 "" → ""（脱掉）；非空字符串 → 装备该物品
                success, error_detail = activate_equip_item(
                    rpg_game,
                    weapon=payload.arguments.get("weapon"),
                    armor=payload.arguments.get("armor"),
                    accessory=payload.arguments.get("accessory"),
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

        # 第一步：从文件加载地下城并创建实体（幂等）
        success, error_detail = setup_dungeon(rpg_game, payload.dungeon_name)
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

    在家园状态下触发地下城文本与图片的生成流程（dungeon_generate_pipeline）。
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

    # 创建 dungeon generate pipeline 后台任务（在锁外创建，让任务在后台独立持锁执行）
    generate_dungeon_task = game_server.create_task()

    asyncio.create_task(
        _execute_dungeon_generate_pipeline_task(
            generate_dungeon_task.task_id,
            payload.user_name,
            game_server,
        )
    )

    logger.info(
        f"📝 创建 dungeon generate pipeline 任务: task_id={generate_dungeon_task.task_id}, user={payload.user_name}"
    )

    return HomeGenerateDungeonResponse(
        task_id=generate_dungeon_task.task_id,
        status=TaskStatus.RUNNING.value,
        message="dungeon generate pipeline 任务已启动，请通过会话消息查询结果",
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@home_gameplay_api_router.post(
    path="/api/home/roster/add/v1/", response_model=HomeRosterAddResponse
)
async def add_party_member_endpoint(
    payload: HomeRosterAddRequest,
    game_server: CurrentGameServer,
) -> HomeRosterAddResponse:
    current_room = game_server.get_room(payload.user_name)
    if current_room is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"找不到游戏房间: user={payload.user_name}",
        )
    async with current_room._lock:
        tcg_game = await _validate_player_at_home(payload.user_name, game_server)
        success, error_detail = add_party_member(tcg_game, payload.member_name)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_detail,
            )
    return HomeRosterAddResponse(message=f"已将 {payload.member_name} 加入远征队")


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@home_gameplay_api_router.post(
    path="/api/home/roster/remove/v1/", response_model=HomeRosterRemoveResponse
)
async def remove_party_member_endpoint(
    payload: HomeRosterRemoveRequest,
    game_server: CurrentGameServer,
) -> HomeRosterRemoveResponse:
    current_room = game_server.get_room(payload.user_name)
    if current_room is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"找不到游戏房间: user={payload.user_name}",
        )
    async with current_room._lock:
        tcg_game = await _validate_player_at_home(payload.user_name, game_server)
        success, error_detail = remove_party_member(tcg_game, payload.member_name)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_detail,
            )
    return HomeRosterRemoveResponse(message=f"已将 {payload.member_name} 从远征队移除")


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@home_gameplay_api_router.post(
    path="/api/home/craft_item/v1/", response_model=HomeCraftItemResponse
)
async def home_craft_item(
    payload: HomeCraftItemRequest,
    game_server: CurrentGameServer,
) -> HomeCraftItemResponse:
    """
    家园制造物品接口

    根据提交的材料列表调用 LLM 制造消耗品，写入背包并消耗对应材料。

    Args:
        payload: 制造请求对象，包含材料名称列表
        game_server: 游戏服务器实例

    Returns:
        HomeCraftItemResponse: 包含 task_id 的异步任务响应

    Raises:
        HTTPException(404): 玩家未登录或游戏实例不存在
        HTTPException(400): 玩家不在家园状态或材料不足
    """

    logger.info(f"/api/home/craft_item/v1/: {payload.model_dump_json()}")

    current_room = game_server.get_room(payload.user_name)
    if current_room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    async with current_room._lock:
        rpg_game = await _validate_player_at_home(
            payload.user_name,
            game_server,
        )
        success, error_detail = activate_craft_item(rpg_game, payload.materials)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_detail,
            )

    craft_task = game_server.create_task()

    asyncio.create_task(
        _execute_home_pipeline_task(
            craft_task.task_id,
            payload.user_name,
            game_server,
        )
    )

    logger.info(
        f"📝 创建 craft_item 任务: task_id={craft_task.task_id}, user={payload.user_name}"
    )

    return HomeCraftItemResponse(
        task_id=craft_task.task_id,
        status=TaskStatus.RUNNING.value,
        message="craft_item 任务已启动，请通过会话消息查询结果",
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
