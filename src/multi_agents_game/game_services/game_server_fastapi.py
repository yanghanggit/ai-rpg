from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..game_services.dungeon_gameplay_services import dungeon_gameplay_router
from ..game_services.home_gameplay_services import home_gameplay_router
from ..game_services.login_services import login_router
from ..game_services.start_services import start_router
from ..game_services.url_config_services import url_config_router
from ..game_services.view_actor_services import view_actor_router
from ..game_services.view_dungeon_services import view_dungeon_router
from ..game_services.view_home_services import view_home_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router=url_config_router)
app.include_router(router=login_router)
app.include_router(router=start_router)
app.include_router(router=home_gameplay_router)
app.include_router(router=dungeon_gameplay_router)
app.include_router(router=view_dungeon_router)
app.include_router(router=view_home_router)
app.include_router(router=view_actor_router)
