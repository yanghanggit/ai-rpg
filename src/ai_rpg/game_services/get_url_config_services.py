from fastapi import APIRouter, Request
from loguru import logger
from ..models import (
    URLConfigResponse,
)

################################################################################################################
get_url_config_api_router = APIRouter()


################################################################################################################
################################################################################################################
################################################################################################################
@get_url_config_api_router.get(path="/config", response_model=URLConfigResponse)
async def get_url_config(
    request: Request,
) -> URLConfigResponse:

    logger.info("获取API路由")
    base_url = str(request.base_url)
    logger.info(f"URLConfigurationResponse: {base_url}")

    # 获取请求的基础URL（含http(s)://域名）
    # 'http://192.168.192.121:8000/' ?
    return URLConfigResponse(
        message="game server url configuration",
        version="0.0.1",
        endpoints={
            "LOGIN_URL": base_url + "api/login/v1/",
            "LOGOUT_URL": base_url + "api/logout/v1/",
            "START_URL": base_url + "api/start/v1/",
            "HOME_GAMEPLAY_URL": base_url + "api/home/gameplay/v1/",
            "HOME_TRANS_DUNGEON_URL": base_url + "api/home/trans_dungeon/v1/",
            "DUNGEON_GAMEPLAY_URL": base_url + "api/dungeon/gameplay/v1/",
            "DUNGEON_TRANS_HOME_URL": base_url + "api/dungeon/trans_home/v1/",
            "HOME_STATE_URL": base_url + "api/homes/v1/",
            "DUNGEON_STATE_URL": base_url + "api/dungeons/v1/",
            "ACTOR_DETAILS_URL": base_url + "api/actors/v1/",
        },
    )


################################################################################################################
################################################################################################################
################################################################################################################
