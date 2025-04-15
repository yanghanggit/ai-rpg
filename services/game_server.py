from dataclasses import dataclass
from typing import Optional, Final
from services.room_manager import RoomManager
from fastapi import FastAPI
import os


###############################################################################################################################################
@dataclass
class ServerConfig:
    server_ip_address: str
    server_port: int
    local_network_ip: str


###############################################################################################################################################
class GameServer:

    _singleton: Optional["GameServer"] = None

    def __init__(
        self, fast_api: FastAPI, room_manager: RoomManager, server_config: ServerConfig
    ) -> None:
        self._fast_api: Final[FastAPI] = fast_api
        self._room_manager: Final[RoomManager] = room_manager
        self._server_config: Final[ServerConfig] = server_config

    ###############################################################################################################################################
    @property
    def room_manager(self) -> RoomManager:
        return self._room_manager

    ###############################################################################################################################################
    @property
    def server_config(self) -> ServerConfig:
        return self._server_config

    ###############################################################################################################################################
    @property
    def server_ip_address(self) -> str:
        return self._server_config.server_ip_address

    ###############################################################################################################################################
    @property
    def server_port(self) -> int:
        return self._server_config.server_port

    ###############################################################################################################################################
    @property
    def local_network_ip(self) -> str:
        return self._server_config.local_network_ip

    ###############################################################################################################################################
    @property
    def fast_api(self) -> FastAPI:
        return self._fast_api

    ###############################################################################################################################################
    @property
    def pid(self) -> int:
        return os.getpid()

    ###############################################################################################################################################
