from fastapi import APIRouter
from loguru import logger
from game_services.game_server_instance import GameServerInstance
from models_v_0_0_1 import (
    APIEndpointConfiguration,
    APIEndpointConfigurationResponse,
)


api_endpoints_router = APIRouter()


@api_endpoints_router.get(
    path="/api_endpoints/v1/", response_model=APIEndpointConfigurationResponse
)
async def api_endpoints(
    game_server: GameServerInstance,
) -> APIEndpointConfigurationResponse:

    logger.info("获取API路由")

    server_ip_address = str(game_server.server_ip_address)
    if server_ip_address == "0.0.0.0":
        # TODO, 这里需要改成获取本机的ip地址
        server_ip_address = game_server.local_network_ip
        logger.info(f"0.0.0.0, use local ip address: {server_ip_address}")

    server_port = game_server.server_port

    generated_api_endpoints: APIEndpointConfiguration = APIEndpointConfiguration(
        # 测试
        TEST_URL=f"http://{server_ip_address}:{server_port}/test/v1/",
        # 核心流程
        LOGIN_URL=f"http://{server_ip_address}:{server_port}/login/v1/",
        LOGOUT_URL=f"http://{server_ip_address}:{server_port}/logout/v1/",
        START_URL=f"http://{server_ip_address}:{server_port}/start/v1/",
        # Home 流程
        HOME_GAMEPLAY_URL=f"http://{server_ip_address}:{server_port}/home/gameplay/v1/",
        HOME_TRANS_DUNGEON_URL=f"http://{server_ip_address}:{server_port}/home/trans_dungeon/v1/",
        # Dungeon 流程
        DUNGEON_GAMEPLAY_URL=f"http://{server_ip_address}:{server_port}/dungeon/gameplay/v1/",
        DUNGEON_TRANS_HOME_URL=f"http://{server_ip_address}:{server_port}/dungeon/trans_home/v1/",
        # View方法
        VIEW_HOME_URL=f"http://{server_ip_address}:{server_port}/view-home/v1/",
        VIEW_DUNGEON_URL=f"http://{server_ip_address}:{server_port}/view-dungeon/v1/",
        VIEW_ACTOR_URL=f"http://{server_ip_address}:{server_port}/view-actor/v1/",
    )

    return APIEndpointConfigurationResponse(
        message="获取API路由成功",
        api_endpoints=generated_api_endpoints,
    )
