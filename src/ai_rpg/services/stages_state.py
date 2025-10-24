from fastapi import APIRouter, HTTPException, status
from loguru import logger
from .game_server_depends import GameServerInstance
from ..models import (
    StagesStateResponse,
)
from ..game.rpg_game import RPGGame

###################################################################################################################################################################
stages_state_api_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@stages_state_api_router.get(
    path="/api/stages/v1/{user_name}/{game_name}/state",
    response_model=StagesStateResponse,
)
async def get_stages_state(
    game_server: GameServerInstance,
    user_name: str,
    game_name: str,
) -> StagesStateResponse:

    logger.info(f"get_stages_state: {user_name}, {game_name}")
    try:

        # 是否有房间？！！
        if not game_server.has_room(user_name):
            logger.error(f"view_home: {user_name} has no room")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="没有房间",
            )

        # 是否有游戏？！！
        current_room = game_server.get_room(user_name)
        assert current_room is not None

        # 获取游戏实例
        web_game: RPGGame | None = None

        # 获取增量消息
        if (
            current_room._sdg_game is not None
            and game_name == current_room._sdg_game.name
        ):
            # 获取游戏
            web_game = current_room._sdg_game

        elif (
            current_room._tcg_game is not None
            and game_name == current_room._tcg_game.name
        ):
            # 获取游戏
            web_game = current_room._tcg_game

        else:
            logger.error(f"get_session_messages: {user_name} game_name mismatch")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="游戏名称不匹配",
            )

        # 获取所有角色实体
        assert web_game is not None, "WebGame should not be None"

        # 获取当前地图
        mapping_data = web_game.get_stage_actor_distribution_mapping()
        logger.info(f"view_home: {user_name} mapping_data: {mapping_data}")

        # 返回。
        return StagesStateResponse(
            mapping=mapping_data,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务器错误: {str(e)}",
        )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
