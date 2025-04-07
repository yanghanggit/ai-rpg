from fastapi import APIRouter
from loguru import logger
from services.game_server_instance import GameServerInstance
from models_v_0_0_1 import (
    APIEndpointConfiguration,
    APIEndpointConfigurationRequest,
    APIEndpointConfigurationResponse,
)


api_endpoints_router = APIRouter()


@api_endpoints_router.post(
    path="/api_endpoints/v1/", response_model=APIEndpointConfigurationResponse
)
async def api_endpoints(
    request_data: APIEndpointConfigurationRequest,
    game_server: GameServerInstance,
) -> APIEndpointConfigurationResponse:

    logger.info(f"api_endpoints: {request_data.model_dump_json()}")

    server_ip_address = game_server.server_ip_address
    server_port = game_server.server_port

    generated_api_endpoints: APIEndpointConfiguration = APIEndpointConfiguration(
        TEST_URL=f"http://{server_ip_address}:{server_port}/test/v1/",
        LOGIN_URL=f"http://{server_ip_address}:{server_port}/login/v1/",
        LOGOUT_URL=f"http://{server_ip_address}:{server_port}/logout/v1/",
        START_URL=f"http://{server_ip_address}:{server_port}/start/v1/",
        HOME_RUN_URL=f"http://{server_ip_address}:{server_port}/home/run/v1/",
        HOME_TRANS_DUNGEON_URL=f"http://{server_ip_address}:{server_port}/home/trans_dungeon/v1/",
        DUNGEON_RUN_URL=f"http://{server_ip_address}:{server_port}/dungeon/run/v1/",
        VIEW_DUNGEON_URL=f"http://{server_ip_address}:{server_port}/view-dungeon/v1/",
    )

    return APIEndpointConfigurationResponse(
        message="获取API路由成功",
        api_endpoints=generated_api_endpoints,
    )
