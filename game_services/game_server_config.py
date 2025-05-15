from dataclasses import dataclass


@dataclass
class GameServerConfig:
    server_ip_address: str = "0.0.0.0"
    server_port: int = 8000
    local_network_ip: str = "192.168.192.100"
