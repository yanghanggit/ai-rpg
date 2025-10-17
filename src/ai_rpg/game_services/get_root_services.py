from fastapi import APIRouter, Request
from loguru import logger
from ..models import (
    RootResponse,
)

################################################################################################################
get_root_api_router = APIRouter()


################################################################################################################
################################################################################################################
################################################################################################################
@get_root_api_router.get(path="/", response_model=RootResponse)
async def get_url_config(
    request: Request,
) -> RootResponse:

    # logger.info("获取API路由")
    base_url = str(request.base_url)
    logger.info(f"获取API路由 RootResponse: {base_url}")

    from datetime import datetime

    # 获取请求的基础URL（含http(s)://域名）
    # 'http://192.168.192.121:8000/' ?
    return RootResponse(
        service="AI RPG TCG Game Server",
        description="AI RPG TCG Game Server API Root Endpoint",
        status="healthy",
        timestamp=datetime.now().isoformat(),
        version="0.0.1",
        endpoints={
            "login": base_url + "api/login/v1/",
            "logout": base_url + "api/logout/v1/",
            "start": base_url + "api/start/v1/",
            "home_gameplay": base_url + "api/home/gameplay/v1/",
            "home_trans_dungeon": base_url + "api/home/trans_dungeon/v1/",
            "dungeon_gameplay": base_url + "api/dungeon/gameplay/v1/",
            "dungeon_trans_home": base_url + "api/dungeon/trans_home/v1/",
            "home_state": base_url + "api/homes/v1/",
            "dungeon_state": base_url + "api/dungeons/v1/",
            "actor_details": base_url + "api/actors/v1/",
            "werewolf_game_start": base_url + "api/werewolf/start/v1/",
            "werewolf_gameplay": base_url + "api/werewolf/gameplay/v1/",
            "werewolf_game_state": base_url + "api/werewolf/state/v1/",
            "werewolf_game_actor_details": base_url + "api/werewolf/actors/v1/",
        },
    )


################################################################################################################
################################################################################################################
################################################################################################################
