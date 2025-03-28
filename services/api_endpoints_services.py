from fastapi import APIRouter
from loguru import logger
from services.game_server_instance import GameServerInstance
from models.api_models import (
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

    logger.debug(f"api_endpoints: {request_data.content}")

    server_ip_address = game_server.server_ip_address
    server_port = game_server.server_port

    generated_api_endpoints: APIEndpointConfiguration = APIEndpointConfiguration(
        TEST_URL=f"http://{server_ip_address}:{server_port}/test/v1/",
        LOGIN_URL=f"http://{server_ip_address}:{server_port}/login/v1/",
        LOGOUT_URL=f"http://{server_ip_address}:{server_port}/logout/v1/",
    )

    return APIEndpointConfigurationResponse(
        message=request_data.content,
        api_endpoints=generated_api_endpoints,
    )
