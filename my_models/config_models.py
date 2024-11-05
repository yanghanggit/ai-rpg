from typing import List, Dict, List
from pydantic import BaseModel


class OneGameConfigModel(BaseModel):
    game_name: str = ""
    about_game: str = ""
    players: Dict[str, str] = {}


class GenGamesConfigModel(BaseModel):
    game_configs: List[OneGameConfigModel] = []


class APIRoutesConfigModel(BaseModel):
    LOGIN: str = ""
    CREATE: str = ""
    JOIN: str = ""
    START: str = ""
    EXIT: str = ""
    EXECUTE: str = ""
    WATCH: str = ""
    CHECK: str = ""
    FETCH_MESSAGES: str = ""
    GET_ACTOR_ARCHIVES: str = ""
    GET_STAGE_ARCHIVES: str = ""


class GameAgentsConfigModel(BaseModel):
    actors: List[Dict[str, str]]
    stages: List[Dict[str, str]]
    world_systems: List[Dict[str, str]]
