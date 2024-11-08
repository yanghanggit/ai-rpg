from fastapi import APIRouter
from loguru import logger
from ws_config import (
    WS_CONFIG,
    APIRoutesConfigRequest,
    APIRoutesConfigResponse,
)
from typing import Dict, Any
from my_models.config_models import (
    APIRoutesConfigModel,
)


api_routes_router = APIRouter()


###############################################################################################################################################
@api_routes_router.post("/api_routes/")
async def api_routes(request_data: APIRoutesConfigRequest) -> Dict[str, Any]:
    logger.info(f"api_routes: {request_data.content}")

    gen_api_routes_config: APIRoutesConfigModel = APIRoutesConfigModel(
        LOGIN=f"http://{WS_CONFIG.LOCAL_HOST}:{WS_CONFIG.PORT}/login/",
        CREATE=f"http://{WS_CONFIG.LOCAL_HOST}:{WS_CONFIG.PORT}/create/",
        JOIN=f"http://{WS_CONFIG.LOCAL_HOST}:{WS_CONFIG.PORT}/join/",
        START=f"http://{WS_CONFIG.LOCAL_HOST}:{WS_CONFIG.PORT}/start/",
        EXIT=f"http://{WS_CONFIG.LOCAL_HOST}:{WS_CONFIG.PORT}/exit/",
        EXECUTE=f"http://{WS_CONFIG.LOCAL_HOST}:{WS_CONFIG.PORT}/execute/",
        WATCH=f"http://{WS_CONFIG.LOCAL_HOST}:{WS_CONFIG.PORT}/watch/",
        CHECK=f"http://{WS_CONFIG.LOCAL_HOST}:{WS_CONFIG.PORT}/check/",
        FETCH_MESSAGES=f"http://{WS_CONFIG.LOCAL_HOST}:{WS_CONFIG.PORT}/fetch_messages/",
        RETRIEVE_ACTOR_ARCHIVES=f"http://{WS_CONFIG.LOCAL_HOST}:{WS_CONFIG.PORT}/retrieve_actor_archives/",
        RETRIEVE_STAGE_ARCHIVES=f"http://{WS_CONFIG.LOCAL_HOST}:{WS_CONFIG.PORT}/retrieve_stage_archives/",
    )

    return APIRoutesConfigResponse(
        message=request_data.content,
        api_routes=gen_api_routes_config,
    ).model_dump()
