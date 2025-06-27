import subprocess
import os


def kill_port(port: int) -> None:
    """终止占用指定端口的进程"""
    try:
        # 查找占用端口的进程
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"], capture_output=True, text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split("\n")
            for pid in pids:
                if pid:
                    print(f"终止端口 {port} 上的进程 PID: {pid}")
                    subprocess.run(["kill", "-9", pid])
    except Exception as e:
        print(f"清理端口 {port} 时出错: {e}")


def main() -> None:
    from multi_agents_game.config.server_config import game_server_port
    from multi_agents_game.game_services.game_server_fastapi import app
    import uvicorn

    # 清理端口
    print(f"检查并清理端口 {game_server_port}...")
    kill_port(game_server_port)

    print(f"启动游戏服务器，端口: {game_server_port}")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=game_server_port,
    )


if __name__ == "__main__":
    main()
