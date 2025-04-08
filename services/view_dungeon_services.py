from fastapi import APIRouter
from services.game_server_instance import GameServerInstance
from models_v_0_0_1 import (
    ViewDungeonRequest,
    ViewDungeonData,
    ViewDungeonResponse,
)
from loguru import logger


###################################################################################################################################################################
view_dungeon_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@view_dungeon_router.post(path="/view-dungeon/v1/", response_model=ViewDungeonResponse)
async def view_dungeon(
    request_data: ViewDungeonRequest,
    game_server: GameServerInstance,
) -> ViewDungeonResponse:

    logger.info(f"/view-dungeon/v1/: {request_data.model_dump_json()}")

    # 是否有房间？！！
    room_manager = game_server.room_manager
    if not room_manager.has_room(request_data.user_name):
        logger.error(
            f"home_run: {request_data.user_name} has no room, please login first."
        )
        return ViewDungeonResponse(
            error=1001,
            message="没有登录，请先登录",
        )

    # 是否有游戏？！！
    current_room = room_manager.get_room(request_data.user_name)
    assert current_room is not None
    if current_room._game is None:
        logger.error(
            f"home_run: {request_data.user_name} has no game, please login first."
        )
        return ViewDungeonResponse(
            error=1002,
            message="没有游戏，请先登录",
        )

    # 判断游戏是否开始
    if not current_room._game.is_game_started:
        logger.error(
            f"home_run: {request_data.user_name} game not started, please start it first."
        )
        return ViewDungeonResponse(
            error=1003,
            message="游戏没有开始，请先开始游戏",
        )

    # 创建返回数据。
    view_data = ViewDungeonData(
        dungeon_name=current_room._game.current_dungeon.name,
        levels=[stage.name for stage in current_room._game.current_dungeon.levels],
        current_position=current_room._game.current_dungeon.position,
    )

    # 如果已经正常进入了副本，获取当前副本的演员列表。
    current_level = current_room._game.current_dungeon.current_level()
    if current_level is not None:
        assert view_data.current_position >= 0, "current_position should be >= 0"

        mapping_data = current_room._game.retrieve_stage_actor_names_mapping(
            include_home=False, include_dungeon=True
        )
        logger.info(f"home_run: {request_data.user_name} mapping_data: {mapping_data}")
        assert (
            current_level.name in mapping_data
        ), f"current_level: {current_level.name} not in mapping_data: {mapping_data}"
        view_data.current_actors_in_level = mapping_data.get(current_level.name, [])
        view_data.combat_phase = current_room._game.current_engagement.combat_phase
        view_data.combat_result = current_room._game.current_engagement.combat_result

    # 返回。
    return ViewDungeonResponse(
        data=view_data,
        error=0,
        message=view_data.model_dump_json(),
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
