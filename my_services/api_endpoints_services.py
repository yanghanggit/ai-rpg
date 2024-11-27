from fastapi import APIRouter
from loguru import logger
from ws_config import (
    WsConfig,
    APIEndpointsConfigRequest,
    APIEndpointsConfigResponse,
)
from typing import Dict, Any
from my_models.config_models import (
    APIEndpointsConfigModel,
)


api_endpoints_router = APIRouter()


###############################################################################################################################################
@api_endpoints_router.post("/api_endpoints/")
async def api_endpoints(request_data: APIEndpointsConfigRequest) -> Dict[str, Any]:
    logger.info(f"api_endpoints: {request_data.content}")

    gen_api_endpoints_config: APIEndpointsConfigModel = APIEndpointsConfigModel(
        LOGIN=f"http://{WsConfig.LOCALHOST}:{WsConfig.DEFAULT_PORT}/login/",
        CREATE=f"http://{WsConfig.LOCALHOST}:{WsConfig.DEFAULT_PORT}/create/",
        JOIN=f"http://{WsConfig.LOCALHOST}:{WsConfig.DEFAULT_PORT}/join/",
        START=f"http://{WsConfig.LOCALHOST}:{WsConfig.DEFAULT_PORT}/start/",
        EXIT=f"http://{WsConfig.LOCALHOST}:{WsConfig.DEFAULT_PORT}/exit/",
        EXECUTE=f"http://{WsConfig.LOCALHOST}:{WsConfig.DEFAULT_PORT}/execute/",
        SURVEY_STAGE_ACTION=f"http://{WsConfig.LOCALHOST}:{WsConfig.DEFAULT_PORT}/survey_stage_action/",
        STATUS_INVENTORY_CHECK_ACTION=f"http://{WsConfig.LOCALHOST}:{WsConfig.DEFAULT_PORT}/status_inventory_check_action/",
        FETCH_MESSAGES=f"http://{WsConfig.LOCALHOST}:{WsConfig.DEFAULT_PORT}/fetch_messages/",
        RETRIEVE_ACTOR_ARCHIVES=f"http://{WsConfig.LOCALHOST}:{WsConfig.DEFAULT_PORT}/retrieve_actor_archives/",
        RETRIEVE_STAGE_ARCHIVES=f"http://{WsConfig.LOCALHOST}:{WsConfig.DEFAULT_PORT}/retrieve_stage_archives/",
    )

    return APIEndpointsConfigResponse(
        message=request_data.content,
        api_endpoints=gen_api_endpoints_config,
    ).model_dump()
