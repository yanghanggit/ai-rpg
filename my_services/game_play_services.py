from fastapi import APIRouter
from loguru import logger
from ws_config import (
    SurveyStageRequest,
    SurveyStageResponse,
    StatusInventoryCheckRequest,
    StatusInventoryCheckResponse,
    RetrieveActorArchivesRequest,
    RetrieveActorArchivesResponse,
    RetrieveStageArchivesRequest,
    RetrieveStageArchivesResponse,
)
from typing import Dict, Any
from my_services.room_manager import RoomManagerInstance
import rpg_game.rpg_game_utils


game_play_api_router = APIRouter()


###############################################################################################################################################
@game_play_api_router.post("/survey_stage_action/")
async def survey_stage_action(request_data: SurveyStageRequest) -> Dict[str, Any]:

    room = RoomManagerInstance.get_room(request_data.user_name)
    if room is None or room.game is None:
        return SurveyStageResponse(
            user_name=request_data.user_name,
            game_name=request_data.game_name,
            actor_name=request_data.actor_name,
            error=1,
            message="room is None",
        ).model_dump()

    # 没有客户端就不能看
    player_proxy = room.get_player()
    assert player_proxy is not None
    if player_proxy is None:
        return SurveyStageResponse(
            user_name=request_data.user_name,
            game_name=request_data.game_name,
            actor_name=request_data.actor_name,
            error=1,
            message="player_proxy is None",
        ).model_dump()

    # 获得消息
    watch_action_model = rpg_game.rpg_game_utils.gen_player_survey_stage_model(
        room.game, player_proxy
    )

    if watch_action_model is None:
        return SurveyStageResponse(
            user_name=request_data.user_name,
            game_name=request_data.game_name,
            actor_name=request_data.actor_name,
            error=2,
            message="watch_action_model is None",
        ).model_dump()

    # 返回观察游戏的信息
    return SurveyStageResponse(
        user_name=request_data.user_name,
        game_name=request_data.game_name,
        actor_name=request_data.actor_name,
        action_model=watch_action_model,
    ).model_dump()


###############################################################################################################################################
@game_play_api_router.post("/status_inventory_check_action/")
async def status_inventory_check_action(
    request_data: StatusInventoryCheckRequest,
) -> Dict[str, Any]:

    room = RoomManagerInstance.get_room(request_data.user_name)
    if room is None or room.game is None:
        return StatusInventoryCheckResponse(
            user_name=request_data.user_name,
            game_name=request_data.game_name,
            actor_name=request_data.actor_name,
            error=100,
            message="game_room._game is None",
        ).model_dump()

    # 没有客户端就不能看
    player_proxy = room.get_player()
    if player_proxy is None:
        return StatusInventoryCheckResponse(
            user_name=request_data.user_name,
            game_name=request_data.game_name,
            actor_name=request_data.actor_name,
            error=1,
            message="player_proxy is None",
        ).model_dump()

    # 获得消息
    check_action_model = (
        rpg_game.rpg_game_utils.gen_player_status_inventory_check_model(
            room.game, player_proxy
        )
    )

    if check_action_model is None:
        return StatusInventoryCheckResponse(
            user_name=request_data.user_name,
            game_name=request_data.game_name,
            actor_name=request_data.actor_name,
            error=2,
            message="check_action_model is None",
        ).model_dump()

    # 返回检查游戏的信息
    return StatusInventoryCheckResponse(
        user_name=request_data.user_name,
        game_name=request_data.game_name,
        actor_name=request_data.actor_name,
        action_model=check_action_model,
    ).model_dump()


###############################################################################################################################################
@game_play_api_router.post("/retrieve_actor_archives/")
async def retrieve_actor_archives(
    request_data: RetrieveActorArchivesRequest,
) -> Dict[str, Any]:

    room = RoomManagerInstance.get_room(request_data.user_name)
    if room is None or room.game is None:
        return RetrieveActorArchivesResponse(
            user_name=request_data.user_name,
            game_name=request_data.game_name,
            actor_name=request_data.actor_name,
            error=100,
            message="game_room._game is None",
        ).model_dump()

    # 没有客户端就不能看
    player_proxy = room.get_player()
    if player_proxy is None:
        return RetrieveActorArchivesResponse(
            user_name=request_data.user_name,
            game_name=request_data.game_name,
            actor_name=request_data.actor_name,
            error=1,
            message="player_proxy is None",
        ).model_dump()

    # 获得消息
    retrieve_actor_archives_action_model = (
        rpg_game.rpg_game_utils.gen_player_retrieve_actor_archives_action_model(
            room.game, player_proxy
        )
    )

    if retrieve_actor_archives_action_model is None:
        return RetrieveActorArchivesResponse(
            user_name=request_data.user_name,
            game_name=request_data.game_name,
            actor_name=request_data.actor_name,
            error=2,
            message="retrieve_actor_archives_action_model is None",
        ).model_dump()

    return RetrieveActorArchivesResponse(
        user_name=request_data.user_name,
        game_name=request_data.game_name,
        actor_name=request_data.actor_name,
        action_model=retrieve_actor_archives_action_model,
    ).model_dump()


###############################################################################################################################################
@game_play_api_router.post("/retrieve_stage_archives/")
async def retrieve_stage_archives(
    request_data: RetrieveStageArchivesRequest,
) -> Dict[str, Any]:

    room = RoomManagerInstance.get_room(request_data.user_name)
    if room is None or room.game is None:
        return RetrieveStageArchivesResponse(
            user_name=request_data.user_name,
            game_name=request_data.game_name,
            actor_name=request_data.actor_name,
            error=100,
            message="game_room._game is None",
        ).model_dump()

    player_proxy = room.get_player()
    if player_proxy is None:
        return RetrieveStageArchivesResponse(
            user_name=request_data.user_name,
            game_name=request_data.game_name,
            actor_name=request_data.actor_name,
            error=1,
            message="player_proxy is None",
        ).model_dump()

    retrieve_stage_archives_action_model = (
        rpg_game.rpg_game_utils.gen_player_retrieve_stage_archives_action_model(
            room.game, player_proxy
        )
    )

    if retrieve_stage_archives_action_model is None:
        return RetrieveStageArchivesResponse(
            user_name=request_data.user_name,
            game_name=request_data.game_name,
            actor_name=request_data.actor_name,
            error=2,
            message="retrieve_stage_archives_action_model is None",
        ).model_dump()

    return RetrieveStageArchivesResponse(
        user_name=request_data.user_name,
        game_name=request_data.game_name,
        actor_name=request_data.actor_name,
        action_model=retrieve_stage_archives_action_model,
    ).model_dump()


###############################################################################################################################################
