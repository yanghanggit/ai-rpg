"""
副本生命周期 API 路由模块（进入、关卡推进、退出等与具体房间类型无关的流程接口）
"""

from fastapi import APIRouter, HTTPException, status
from loguru import logger
from ..game.dbg_game import DBGGame
from .game_server_dependencies import CurrentGameServer
from ..models import (
    DungeonAdvanceStageRequest,
    DungeonAdvanceStageResponse,
    DungeonExitRequest,
    DungeonExitResponse,
    HomeEnterDungeonRequest,
    HomeEnterDungeonResponse,
)
from .dungeon_advance import (
    advance_dungeon,
)
from .dungeon_enter import (
    enter_dungeon,
)
from .dungeon_exit import (
    exit_dungeon,
)
from .dungeon_setup import (
    setup_dungeon,
    teardown_dungeon,
)
from .home_tasks import (
    _validate_player_at_home,
)
from ..game.game_server import GameServer

###################################################################################################################################################################
dungeon_lifecycle_api_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
def _validate_dungeon_prerequisites(
    user_name: str,
    game_server: GameServer,
) -> DBGGame:
    """
    验证副本操作的前置条件
    """

    # 1. 验证房间存在（玩家已登录）
    if not game_server.has_room(user_name):
        logger.error(f"副本操作失败: 玩家 {user_name} 未登录")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    current_room = game_server.get_room(user_name)
    assert (
        current_room is not None
    ), f"_validate_dungeon_prerequisites: room is None for {user_name}"

    # 2. 验证游戏实例存在
    if current_room._dbg_game is None:
        logger.error(f"副本操作失败: 玩家 {user_name} 没有游戏实例")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="游戏实例不存在，请重新登录",
        )

    # 3. 获取并验证游戏实例类型
    dbg_game = current_room._dbg_game

    # 4. 验证玩家在副本状态
    if not dbg_game.is_player_in_dungeon_stage:
        logger.error(f"副本操作失败: 玩家 {user_name} 不在副本状态")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能在副本状态下使用",
        )

    return dbg_game


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@dungeon_lifecycle_api_router.post(
    path="/api/dungeon/progress/advance_stage/v1/",
    response_model=DungeonAdvanceStageResponse,
)
async def dungeon_advance_stage(
    payload: DungeonAdvanceStageRequest,
    game_server: CurrentGameServer,
) -> DungeonAdvanceStageResponse:
    """
    副本关卡推进接口
    """

    logger.info(f"/api/dungeon/progress/advance_stage/v1/: user={payload.user_name}")

    # 获取房间并用每玩家锁避免并发状态竞争
    current_room = game_server.get_room(payload.user_name)
    if current_room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    async with current_room._lock:

        # 验证副本操作的前置条件
        rpg_game = _validate_dungeon_prerequisites(
            user_name=payload.user_name,
            game_server=game_server,
        )

        # 若当前为战斗房间，验证战斗是否处于等待阶段（即战斗已结束）
        if rpg_game.is_current_room_combat:
            if not rpg_game.current_combat_room.combat.is_post_combat:
                logger.error(
                    f"玩家 {payload.user_name} 前进下一关失败: 战斗未处于等待阶段"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="战斗未处于等待阶段",
                )

            if rpg_game.current_combat_room.combat.is_lost:
                logger.warning(f"玩家 {payload.user_name} 战斗失败")
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="战斗失败，无法继续",
                )

            if not rpg_game.current_combat_room.combat.is_won:
                logger.error(f"玩家 {payload.user_name} 战斗状态异常: 既未胜利也未失败")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="战斗状态异常",
                )

        # 获取下一房间索引和房间实例，确保存在下一房间，否则无法推进副本
        next_room_index = rpg_game.current_dungeon.current_room_index + 1
        next_room = rpg_game.current_dungeon.get_room(next_room_index)
        if next_room is None:
            logger.error(f"玩家 {payload.user_name} 副本前进失败，没有更多房间")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="副本已全部通关，请返回营地",
            )

        # 推进副本到下一房间
        success, msg = advance_dungeon(rpg_game, rpg_game.current_dungeon)
        if not success:
            logger.error(f"玩家 {payload.user_name} 副本前进失败: {msg}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=msg,
            )

        # 推进副本到下一房间后，返回成功消息
        return DungeonAdvanceStageResponse(message="已前进到下一关")


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@dungeon_lifecycle_api_router.post(
    path="/api/dungeon/exit/v1/", response_model=DungeonExitResponse
)
async def dungeon_exit(
    payload: DungeonExitRequest,
    game_server: CurrentGameServer,
) -> DungeonExitResponse:
    """
    副本退出接口
    """

    logger.info(f"/api/dungeon/exit/v1/: user={payload.user_name}")

    # 获取房间并用每玩家锁避免并发状态竞争
    current_room = game_server.get_room(payload.user_name)
    if current_room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    async with current_room._lock:

        # 验证副本操作的前置条件
        dbg_game = _validate_dungeon_prerequisites(
            user_name=payload.user_name,
            game_server=game_server,
        )

        # 若当前为战斗房间，验证战斗是否已结束
        if dbg_game.is_current_room_combat:
            if not dbg_game.current_combat_room.combat.is_post_combat:
                logger.error(f"玩家 {payload.user_name} 返回家园失败: 战斗未结束")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="只能在战斗结束后回家",
                )

        # 退出副本并返回家园
        success, msg = exit_dungeon(dbg_game, dbg_game._world.dungeon)
        if not success:
            logger.error(f"玩家 {payload.user_name} 退出副本失败: {msg}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=msg,
            )

        # 销毁副本实体并重置副本数据
        teardown_dungeon(dbg_game, dbg_game._world.dungeon)

        logger.info(f"玩家 {payload.user_name} 成功返回家园")

        # 返回
        return DungeonExitResponse(
            message="成功返回家园",
        )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@dungeon_lifecycle_api_router.post(
    path="/api/home/enter_dungeon/v1/", response_model=HomeEnterDungeonResponse
)
async def dungeon_enter(
    payload: HomeEnterDungeonRequest,
    game_server: CurrentGameServer,
) -> HomeEnterDungeonResponse:
    """
    副本进入接口（从家园传送至副本第一关）
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
        # 验证前置条件（玩家必须处于家园模式）
        rpg_game = await _validate_player_at_home(
            payload.user_name,
            game_server,
        )

        # 第一步：从文件加载副本并创建实体（幂等）
        success, error_detail = setup_dungeon(rpg_game, payload.dungeon_name)
        if not success:
            logger.error(f"玩家 {payload.user_name} 副本实体创建失败: {error_detail}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="副本实体创建失败",
            )

        # 第二步：组建远征队并进入第一关
        success, error_detail = enter_dungeon(rpg_game, rpg_game.current_dungeon)
        if not success:
            logger.error(f"玩家 {payload.user_name} 进入副本失败: {error_detail}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="进入副本失败",
            )

        # 返回传送成功响应
        return HomeEnterDungeonResponse(
            message=payload.model_dump_json(),
        )


###################################################################################################################################################################
###################################################################################################################################################################
