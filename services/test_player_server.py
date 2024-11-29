import subprocess
from typing import Dict, TypedDict


class PlayerProcessInfo(TypedDict):
    player_id: str
    process: subprocess.Popen[bytes]
    port: int


player_process_map: Dict[str, PlayerProcessInfo] = {}


###############################################################################################################################################
def start_player_server(
    player_id: str, execute_python: str, host: str, port: int
) -> None:

    process = subprocess.Popen(
        ["python", execute_python, "--host", host, "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    player_process_map[player_id] = {
        "player_id": player_id,
        "process": process,
        "port": port,
    }
    print(f"玩家 {player_id} 的服务端启动在端口 {port}")


###############################################################################################################################################
def stop_player_server(player_id: str) -> None:
    if player_id in player_process_map:
        process_info = player_process_map.pop(player_id)
        process = process_info["process"]
        process.terminate()  # 优雅停止
        process.wait()  # 等待完全退出
        print(f"玩家 {player_id} 的服务端已停止")
    else:
        print(f"未找到玩家 {player_id} 的服务端进程")


###############################################################################################################################################

# 示例启动与停止
if __name__ == "__main__":
    player_id = "player_1"
    start_player_server(
        player_id=player_id,
        execute_python="game_server.py",
        host="127.0.0.1",
        port=8000,
    )

    # 等待一会模拟运行
    # import time

    # while True:
    #     time.sleep(1)
    #     print("running")

    # time.sleep(5)

    # stop_player_server(player_id)
###############################################################################################################################################
