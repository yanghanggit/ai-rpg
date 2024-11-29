from fastapi import APIRouter
from loguru import logger
from models.api_models import (
    APIEndpointsConfigRequest,
    APIEndpointsConfigResponse,
)
from models.config_models import (
    APIEndpointsConfigModel,
)
from services.game_server import GameServer


api_endpoints_router = APIRouter()


@api_endpoints_router.post(
    path="/api_endpoints/", response_model=APIEndpointsConfigResponse
)
async def api_endpoints(
    request_data: APIEndpointsConfigRequest,
) -> APIEndpointsConfigResponse:

    logger.info(f"api_endpoints: {request_data.content}")
    assert GameServer.Instance is not None

    server_ip_address = GameServer.Instance.server_ip_address
    server_port = GameServer.Instance.server_port

    generated_api_endpoints: APIEndpointsConfigModel = APIEndpointsConfigModel(
        LOGIN=f"http://{server_ip_address}:{server_port}/login/",
        CREATE=f"http://{server_ip_address}:{server_port}/create/",
        JOIN=f"http://{server_ip_address}:{server_port}/join/",
        START=f"http://{server_ip_address}:{server_port}/start/",
        EXIT=f"http://{server_ip_address}:{server_port}/exit/",
        EXECUTE=f"http://{server_ip_address}:{server_port}/execute/",
        SURVEY_STAGE_ACTION=f"http://{server_ip_address}:{server_port}/survey_stage_action/",
        STATUS_INVENTORY_CHECK_ACTION=f"http://{server_ip_address}:{server_port}/status_inventory_check_action/",
        FETCH_MESSAGES=f"http://{server_ip_address}:{server_port}/fetch_messages/",
        RETRIEVE_ACTOR_ARCHIVES=f"http://{server_ip_address}:{server_port}/retrieve_actor_archives/",
        RETRIEVE_STAGE_ARCHIVES=f"http://{server_ip_address}:{server_port}/retrieve_stage_archives/",
    )

    return APIEndpointsConfigResponse(
        message=request_data.content,
        api_endpoints=generated_api_endpoints,
    )
