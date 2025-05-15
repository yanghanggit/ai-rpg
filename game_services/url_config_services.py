from fastapi import APIRouter, Request
from loguru import logger
from models_v_0_0_1 import (
    URLConfigurationResponse,
)


url_config_router = APIRouter()


################################################################################################################
################################################################################################################
################################################################################################################
@url_config_router.get(path="/config", response_model=URLConfigurationResponse)
async def api_endpoints(
    request: Request,
) -> URLConfigurationResponse:

    logger.info("获取API路由")
    base = str(request.base_url)
    logger.info(f"URLConfigurationResponse: {base}")

    # 获取请求的基础URL（含http(s)://域名）
    return URLConfigurationResponse(
        api_version="v1",
        endpoints={
            "LOGIN_URL": f"{base}login/v1/",
            "LOGOUT_URL": f"{base}logout/v1/",
            "START_URL": f"{base}start/v1/",
            "HOME_GAMEPLAY_URL": f"{base}home/gameplay/v1/",
            "HOME_TRANS_DUNGEON_URL": f"{base}home/trans_dungeon/v1/",
            "DUNGEON_GAMEPLAY_URL": f"{base}dungeon/gameplay/v1/",
            "DUNGEON_TRANS_HOME_URL": f"{base}dungeon/trans_home/v1/",
            "VIEW_HOME_URL": f"{base}view-home/v1/",
            "VIEW_DUNGEON_URL": f"{base}view-dungeon/v1/",
            "VIEW_ACTOR_URL": f"{base}view-actor/v1/",
        },
    )


################################################################################################################
################################################################################################################
################################################################################################################
