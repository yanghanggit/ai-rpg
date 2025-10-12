from typing import Optional
from fastapi import APIRouter, HTTPException, status
from loguru import logger

# from ..demo.stage_dungeon4 import (
#     create_demo_dungeon4,
# )
from ..game.player_client import PlayerClient
from ..game.tcg_game import TCGGame
from ..game.world_data_service import get_user_world_data, get_game_boot_data
from ..game_services.game_server import GameServerInstance
from ..models import StartRequest, StartResponse, World
from ..mongodb import (
    DungeonDocument,
    mongodb_find_one,
)

###################################################################################################################################################################
start_api_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@start_api_router.post(path="/api/start/v1/", response_model=StartResponse)
async def start(
    request_data: StartRequest,
    game_server: GameServerInstance,
) -> StartResponse:

    logger.info(f"/start/v1/: {request_data.model_dump_json()}")

    try:

        # 如果没有房间，就创建一个
        # room_manager = game_server.room_manager
        if not game_server.has_room(request_data.user_name):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"start/v1: {request_data.user_name} not found, create room",
            )

        # 如果有房间，就获取房间。
        room = game_server.get_room(request_data.user_name)
        assert room is not None

        if room._game is None:

            # 创建玩家客户端
            room._player_client = PlayerClient(
                name=request_data.user_name,
                actor=request_data.actor_name,
            )
            assert room._player_client is not None, "房间玩家客户端实例不存在"

            # 创建游戏
            room._game = setup_web_game_session(
                user=request_data.user_name,
                game=request_data.game_name,
                actor=request_data.actor_name,
                player_client=room._player_client,
            )

            assert room._game is not None, "Web game setup failed"
            if room._game is None:
                logger.error(f"创建游戏失败 = {request_data.game_name}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"start/v1: {request_data.user_name} failed to create game",
                )

            assert room._game is not None, "房间游戏实例不存在"
            assert room._player_client is not None, "房间玩家客户端实例不存在"

            # 初始化游戏
            logger.info(f"start/v1: {request_data.user_name} init game!")
            await room._game.initialize()

        else:
            assert False, "游戏已经在进行中，无法重新启动! 尚未实现！"

        assert room._game is not None
        return StartResponse(
            message=f"启动游戏成功！",
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"start/v1: {request_data.user_name} failed, error: {str(e)}",
        )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
def setup_web_game_session(
    user: str,
    game: str,
    actor: str,
    player_client: PlayerClient,
) -> Optional[TCGGame]:

    world_exists = get_user_world_data(user, game)
    if world_exists is None:

        # 如果没有world数据，就创建一个新的world
        world_boot = get_game_boot_data(game)
        assert world_boot is not None, "world_boot is None"

        # 重新生成world
        world_exists = World(boot=world_boot)

        # 运行时生成地下城系统。
        # "哥布林与兽人"
        # world_exists.dungeon = create_demo_dungeon4()

        # 读数据库! 测试的写死的地下城名字，本质就是dungeon4!!!!
        fixed_dungeon_name = "哥布林与兽人"
        stored_dungeon = mongodb_find_one(
            # DEFAULT_MONGODB_CONFIG.dungeons_collection,
            DungeonDocument.__name__,
            {"dungeon_name": fixed_dungeon_name},
        )
        assert stored_dungeon is not None, "数据库中已经存在该地下城数据"
        logger.success(
            f"从数据库加载地下城{fixed_dungeon_name}数据成功！{stored_dungeon}"
        )
        stored_document = DungeonDocument.from_mongodb(stored_dungeon)
        world_exists.dungeon = stored_document.dungeon_data

    else:
        assert False, "尚未实现从数据库加载world的逻辑"

    # 依赖注入，创建新的游戏
    assert world_exists is not None, "World data must exist to create a game"
    web_game = TCGGame(
        name=game,
        player_client=player_client,
        world=world_exists,
    )

    # 启动游戏的判断，是第一次建立还是恢复？
    if len(web_game.world.entities_serialization) == 0:
        logger.info(f"游戏中没有实体 = {game}, 说明是第一次创建游戏")

        # 直接构建ecs
        web_game.new_game().save()
    else:
        logger.info(f"游戏中有实体 = {game}，需要通过数据恢复实体，是游戏回复的过程")

        # 测试！回复ecs
        web_game.load_game().save()

    # 出现了错误。
    player_entity = web_game.get_player_entity()
    # assert player_entity is not None
    if player_entity is None:
        logger.error(f"没有找到玩家实体 = {actor}")
        return None

    return web_game


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
