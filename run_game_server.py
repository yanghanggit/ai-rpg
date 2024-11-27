from fastapi import FastAPI
from ws_config import (
    WsConfig,
)

from fastapi.middleware.cors import CORSMiddleware
from my_services.api_endpoints_services import api_endpoints_router
from my_services.game_process_services import game_process_api_router
from my_services.game_play_services import game_play_api_router

fastapi_app = FastAPI()
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

fastapi_app.include_router(api_endpoints_router)
fastapi_app.include_router(game_process_api_router)
fastapi_app.include_router(game_play_api_router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(fastapi_app, host=WsConfig.LOCALHOST, port=WsConfig.DEFAULT_PORT)
