from fastapi import APIRouter
from loguru import logger
from ws_config import (
    WS_CONFIG,
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
        LOGIN=f"http://{WS_CONFIG.LOCAL_HOST}:{WS_CONFIG.PORT}/login/",
        CREATE=f"http://{WS_CONFIG.LOCAL_HOST}:{WS_CONFIG.PORT}/create/",
        JOIN=f"http://{WS_CONFIG.LOCAL_HOST}:{WS_CONFIG.PORT}/join/",
        START=f"http://{WS_CONFIG.LOCAL_HOST}:{WS_CONFIG.PORT}/start/",
        EXIT=f"http://{WS_CONFIG.LOCAL_HOST}:{WS_CONFIG.PORT}/exit/",
        EXECUTE=f"http://{WS_CONFIG.LOCAL_HOST}:{WS_CONFIG.PORT}/execute/",
        SURVEY_STAGE_ACTION=f"http://{WS_CONFIG.LOCAL_HOST}:{WS_CONFIG.PORT}/survey_stage_action/",
        STATUS_INVENTORY_CHECK_ACTION=f"http://{WS_CONFIG.LOCAL_HOST}:{WS_CONFIG.PORT}/status_inventory_check_action/",
        FETCH_MESSAGES=f"http://{WS_CONFIG.LOCAL_HOST}:{WS_CONFIG.PORT}/fetch_messages/",
        RETRIEVE_ACTOR_ARCHIVES=f"http://{WS_CONFIG.LOCAL_HOST}:{WS_CONFIG.PORT}/retrieve_actor_archives/",
        RETRIEVE_STAGE_ARCHIVES=f"http://{WS_CONFIG.LOCAL_HOST}:{WS_CONFIG.PORT}/retrieve_stage_archives/",
    )

    return APIEndpointsConfigResponse(
        message=request_data.content,
        api_endpoints=gen_api_endpoints_config,
    ).model_dump()
