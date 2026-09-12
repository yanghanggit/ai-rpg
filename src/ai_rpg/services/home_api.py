"""
家园 API 路由模块

提供家园系统的核心API接口，处理玩家在家园状态下的各种游戏操作，
包括对话、场景切换、游戏推进和副本传送等功能。
"""

from typing import List

from fastapi import APIRouter, HTTPException, status
from loguru import logger

from ..models import (
    HomeAdvanceRequest,
    HomeAdvanceResponse,
    HomeCraftItemRequest,
    HomeCraftItemResponse,
    HomeGenerateDungeonRequest,
    HomeGenerateDungeonResponse,
    HomeItemMoveToInventoryRequest,
    HomeItemMoveToInventoryResponse,
    HomeItemMoveToStorageRequest,
    HomeItemMoveToStorageResponse,
    HomeRemoveCostumeRequest,
    HomeRemoveCostumeResponse,
    HomeRosterAddRequest,
    HomeRosterAddResponse,
    HomeRosterRemoveRequest,
    HomeRosterRemoveResponse,
    HomeSpeakRequest,
    HomeSpeakResponse,
    HomeSwitchStageRequest,
    HomeSwitchStageResponse,
    HomeWearCostumeRequest,
    HomeWearCostumeResponse,
)
from .game_server_dependencies import CurrentGameServer
from .home_actions import (
    activate_craft_consumable,
    activate_craft_costume_item,
    activate_craft_gear_item,
    activate_generate_dungeon,
    activate_plan_action,
    activate_remove_costume,
    activate_speak_action,
    activate_switch_stage,
    activate_wear_costume,
    add_party_member,
    move_item_to_inventory,
    move_item_to_storage,
    remove_party_member,
)
from .home_tasks import (
    _validate_player_at_home,
    execute_dungeon_generate_pipeline_task,
    execute_home_craft_pipeline_task,
    execute_home_pipeline_task,
)

###################################################################################################################################################################
home_api_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@home_api_router.post(
    path="/api/home/player/speak/v1/", response_model=HomeSpeakResponse
)
async def home_player_speak(
    payload: HomeSpeakRequest,
    game_server: CurrentGameServer,
) -> HomeSpeakResponse:
    """
    家园玩家对话接口
    """

    logger.info(f"/api/home/player/speak/v1/: {payload.model_dump_json()}")

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

        # 激活对话动作：玩家与指定NPC进行对话交互
        success, error_detail = activate_speak_action(
            rpg_game,
            target=payload.target,
            content=payload.content,
        )

        # 统一处理动作激活结果
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_detail,
            )

    # 在锁外派发 home pipeline 任务，让任务独立持锁执行
    deferred_job_id = await execute_home_pipeline_task.defer_async(
        user_name=payload.user_name
    )
    job_id = deferred_job_id

    logger.info(
        f"📝 创建 home pipeline 任务: job_id={job_id}, user={payload.user_name}"
    )

    return HomeSpeakResponse(
        job_id=job_id,
        message="home pipeline 任务已启动，请通过会话消息查询结果",
    )


###################################################################################################################################################################
@home_api_router.post(
    path="/api/home/player/switch_stage/v1/", response_model=HomeSwitchStageResponse
)
async def home_player_switch_stage(
    payload: HomeSwitchStageRequest,
    game_server: CurrentGameServer,
) -> HomeSwitchStageResponse:
    """
    家园玩家场景切换接口
    """

    logger.info(f"/api/home/player/switch_stage/v1/: {payload.model_dump_json()}")

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

        # 激活场景切换动作：在家园内切换到不同的场景
        success, error_detail = activate_switch_stage(
            rpg_game, stage_name=payload.stage_name
        )

        # 统一处理动作激活结果
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_detail,
            )

    # 在锁外派发 home pipeline 任务，让任务独立持锁执行
    deferred_job_id = await execute_home_pipeline_task.defer_async(
        user_name=payload.user_name
    )
    job_id = deferred_job_id

    logger.info(
        f"📝 创建 home pipeline 任务: job_id={job_id}, user={payload.user_name}"
    )

    return HomeSwitchStageResponse(
        job_id=job_id,
        message="home pipeline 任务已启动，请通过会话消息查询结果",
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@home_api_router.post(path="/api/home/advance/v1/", response_model=HomeAdvanceResponse)
async def home_advance(
    payload: HomeAdvanceRequest,
    game_server: CurrentGameServer,
) -> HomeAdvanceResponse:
    """
    家园推进接口
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

        # 根据请求参数（payload.actors）为客户端显式指定的角色激活行动计划
        success, error_detail = activate_plan_action(rpg_game, payload.actors)
        if not success:
            # 行动计划激活失败，抛出包含具体错误信息的异常
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_detail,
            )

    # 在锁外派发 home pipeline 任务，让任务独立持锁执行
    deferred_job_id = await execute_home_pipeline_task.defer_async(
        user_name=payload.user_name
    )
    job_id = deferred_job_id

    return HomeAdvanceResponse(
        job_id=job_id,
        message="home pipeline 任务已启动，请通过会话消息查询结果",
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@home_api_router.post(
    path="/api/home/generate_dungeon/v1/", response_model=HomeGenerateDungeonResponse
)
async def home_generate_dungeon(
    payload: HomeGenerateDungeonRequest,
    game_server: CurrentGameServer,
) -> HomeGenerateDungeonResponse:
    """
    家园生成副本接口
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

        # 激活副本生成动作
        success, error_detail = activate_generate_dungeon(rpg_game)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_detail,
            )

    # 在锁外派发 dungeon generate pipeline 任务，让任务独立持锁执行
    deferred_job_id = await execute_dungeon_generate_pipeline_task.defer_async(
        user_name=payload.user_name
    )
    job_id = deferred_job_id

    logger.info(
        f"📝 创建 dungeon generate pipeline 任务: job_id={job_id}, user={payload.user_name}"
    )

    return HomeGenerateDungeonResponse(
        job_id=job_id,
        message="dungeon generate pipeline 任务已启动，请通过会话消息查询结果",
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@home_api_router.post(
    path="/api/home/roster/add/v1/", response_model=HomeRosterAddResponse
)
async def home_add_party_member(
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
        dbg_game = await _validate_player_at_home(payload.user_name, game_server)
        success, error_detail = add_party_member(dbg_game, payload.member_name)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_detail,
            )
    return HomeRosterAddResponse(message=f"已将 {payload.member_name} 加入队伍")


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@home_api_router.post(
    path="/api/home/roster/remove/v1/", response_model=HomeRosterRemoveResponse
)
async def home_remove_party_member(
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
        dbg_game = await _validate_player_at_home(payload.user_name, game_server)
        success, error_detail = remove_party_member(dbg_game, payload.member_name)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_detail,
            )
    return HomeRosterRemoveResponse(message=f"已将 {payload.member_name} 从队伍移除")


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@home_api_router.post(
    path="/api/home/item/move_to_inventory/v1/",
    response_model=HomeItemMoveToInventoryResponse,
)
async def home_item_move_to_inventory(
    payload: HomeItemMoveToInventoryRequest,
    game_server: CurrentGameServer,
) -> HomeItemMoveToInventoryResponse:
    """将道具从储物箱移入随身背包。"""
    current_room = game_server.get_room(payload.user_name)
    if current_room is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"找不到游戏房间: user={payload.user_name}",
        )
    async with current_room._lock:
        dbg_game = await _validate_player_at_home(payload.user_name, game_server)
        moved: List[str] = []
        for name in payload.item_names:
            success, error_detail = move_item_to_inventory(dbg_game, name)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error_detail,
                )
            moved.append(name)
    return HomeItemMoveToInventoryResponse(
        message=f"已将 {', '.join(moved)} 从储物箱移入随身背包"
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@home_api_router.post(
    path="/api/home/item/move_to_storage/v1/",
    response_model=HomeItemMoveToStorageResponse,
)
async def home_item_move_to_storage(
    payload: HomeItemMoveToStorageRequest,
    game_server: CurrentGameServer,
) -> HomeItemMoveToStorageResponse:
    """将道具从随身背包移入储物箱。"""
    current_room = game_server.get_room(payload.user_name)
    if current_room is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"找不到游戏房间: user={payload.user_name}",
        )
    async with current_room._lock:
        dbg_game = await _validate_player_at_home(payload.user_name, game_server)
        moved: List[str] = []
        for name in payload.item_names:
            success, error_detail = move_item_to_storage(dbg_game, name)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error_detail,
                )
            moved.append(name)
    return HomeItemMoveToStorageResponse(
        message=f"已将 {', '.join(moved)} 从随身背包移入储物箱"
    )


###################################################################################################################################################################
###################################################################################################################################################################
@home_api_router.post(
    path="/api/home/costume/wear/v1/", response_model=HomeWearCostumeResponse
)
async def home_wear_costume(
    payload: HomeWearCostumeRequest,
    game_server: CurrentGameServer,
) -> HomeWearCostumeResponse:
    """为指定角色穿上指定时装，触发外观更新 home pipeline 任务。"""
    logger.info(
        f"/api/home/costume/wear/v1/: user={payload.user_name} item={payload.item_name!r} target={payload.target_name!r}"
    )

    current_room = game_server.get_room(payload.user_name)
    if current_room is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"找不到游戏房间: user={payload.user_name}",
        )
    async with current_room._lock:
        dbg_game = await _validate_player_at_home(payload.user_name, game_server)
        success, error_detail = activate_wear_costume(
            dbg_game, payload.item_name, payload.target_name
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_detail,
            )

    deferred_job_id = await execute_home_pipeline_task.defer_async(
        user_name=payload.user_name
    )
    job_id = deferred_job_id
    logger.info(f"📝 创建穿装任务: job_id={job_id}, user={payload.user_name}")
    return HomeWearCostumeResponse(
        job_id=job_id,
        message="穿装任务已启动，请通过会话消息查询结果",
    )


###################################################################################################################################################################
###################################################################################################################################################################
@home_api_router.post(
    path="/api/home/costume/remove/v1/", response_model=HomeRemoveCostumeResponse
)
async def home_remove_costume(
    payload: HomeRemoveCostumeRequest,
    game_server: CurrentGameServer,
) -> HomeRemoveCostumeResponse:
    """为指定角色脱下当前穿戴的时装，触发外观更新 home pipeline 任务。"""
    logger.info(
        f"/api/home/costume/remove/v1/: user={payload.user_name} target={payload.target_name!r}"
    )

    current_room = game_server.get_room(payload.user_name)
    if current_room is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"找不到游戏房间: user={payload.user_name}",
        )
    async with current_room._lock:
        dbg_game = await _validate_player_at_home(payload.user_name, game_server)
        success, error_detail = activate_remove_costume(dbg_game, payload.target_name)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_detail,
            )

    deferred_job_id = await execute_home_pipeline_task.defer_async(
        user_name=payload.user_name
    )
    job_id = deferred_job_id
    logger.info(f"📝 创建脱装任务: job_id={job_id}, user={payload.user_name}")
    return HomeRemoveCostumeResponse(
        job_id=job_id,
        message="脱装任务已启动，请通过会话消息查询结果",
    )


###################################################################################################################################################################
###################################################################################################################################################################


###################################################################################################################################################################
###################################################################################################################################################################
@home_api_router.post(
    path="/api/home/craft/item/v1/", response_model=HomeCraftItemResponse
)
async def home_craft_item(
    payload: HomeCraftItemRequest,
    game_server: CurrentGameServer,
) -> HomeCraftItemResponse:
    """消耗品工坊合成接口：使用储物箱中的材料合成消耗品。"""
    logger.info(
        f"/api/home/craft/item/v1/: user={payload.user_name} materials={payload.materials}"
    )

    current_room = game_server.get_room(payload.user_name)
    if current_room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    async with current_room._lock:
        dbg_game = await _validate_player_at_home(payload.user_name, game_server)
        success, error_detail = activate_craft_consumable(
            dbg_game, list(payload.materials)
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_detail,
            )

    deferred_job_id = await execute_home_craft_pipeline_task.defer_async(
        user_name=payload.user_name
    )
    job_id = deferred_job_id
    logger.info(f"📝 创建消耗品工坐任务: job_id={job_id}, user={payload.user_name}")
    return HomeCraftItemResponse(
        job_id=job_id,
        message="消耗品工坊任务已启动，请通过会话消息查询结果",
    )


###################################################################################################################################################################
###################################################################################################################################################################
@home_api_router.post(
    path="/api/home/craft/gear/v1/", response_model=HomeCraftItemResponse
)
async def home_craft_gear_item(
    payload: HomeCraftItemRequest,
    game_server: CurrentGameServer,
) -> HomeCraftItemResponse:
    """装备工坊锻造接口：使用储物箱中的材料合成装备。"""
    logger.info(
        f"/api/home/craft/gear/v1/: user={payload.user_name} materials={payload.materials}"
    )

    current_room = game_server.get_room(payload.user_name)
    if current_room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    async with current_room._lock:
        dbg_game = await _validate_player_at_home(payload.user_name, game_server)
        success, error_detail = activate_craft_gear_item(
            dbg_game, list(payload.materials)
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_detail,
            )

    deferred_job_id = await execute_home_craft_pipeline_task.defer_async(
        user_name=payload.user_name
    )
    job_id = deferred_job_id
    logger.info(f"📝 创建装备工坐任务: job_id={job_id}, user={payload.user_name}")
    return HomeCraftItemResponse(
        job_id=job_id,
        message="装备工坊任务已启动，请通过会话消息查询结果",
    )


###################################################################################################################################################################
###################################################################################################################################################################
@home_api_router.post(
    path="/api/home/craft/costume/v1/", response_model=HomeCraftItemResponse
)
async def home_craft_costume_item(
    payload: HomeCraftItemRequest,
    game_server: CurrentGameServer,
) -> HomeCraftItemResponse:
    """时装工坊制衣接口：使用储物箱中的材料制作时装。"""
    logger.info(
        f"/api/home/craft/costume/v1/: user={payload.user_name} materials={payload.materials}"
    )

    current_room = game_server.get_room(payload.user_name)
    if current_room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    async with current_room._lock:
        dbg_game = await _validate_player_at_home(payload.user_name, game_server)
        success, error_detail = activate_craft_costume_item(
            dbg_game, list(payload.materials)
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_detail,
            )

    deferred_job_id = await execute_home_craft_pipeline_task.defer_async(
        user_name=payload.user_name
    )
    job_id = deferred_job_id
    logger.info(f"📝 创建时装工坐任务: job_id={job_id}, user={payload.user_name}")
    return HomeCraftItemResponse(
        job_id=job_id,
        message="时装工坊任务已启动，请通过会话消息查询结果",
    )


###################################################################################################################################################################
###################################################################################################################################################################
