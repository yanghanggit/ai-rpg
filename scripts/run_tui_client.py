"""AI RPG 游戏客户端启动脚本（Textual TUI）

终端本地启动：
    uv run python scripts/run_tui_client.py

浏览器访问模式（供局域网/公网访问）：
    uv run python scripts/run_tui_client.py --web
    uv run python scripts/run_tui_client.py --web --port 8080
    然后在浏览器打开 http://localhost:8080

局域网模式（同事可通过你的 IP 访问）：
    # 先查询本机局域网 IP：
    ipconfig getifaddr en0           # 例如得到 192.168.1.100
    # 然后用实际 IP 启动（--public-url 告诉客户端用哪个地址连 WebSocket）：
    uv run python scripts/run_tui_client.py --web --host 0.0.0.0 --port 8080 --public-url http://192.168.1.100:8080
    # 同事浏览器打开 http://192.168.1.100:8080

    python scripts/run_tui_client.py --dev-screen combat-room
    python scripts/run_tui_client.py --dev-screen combat-post-combat

"""

import sys
import os
from datetime import datetime
from typing import Final, Optional, Type
from textual_serve.server import Server
import click
from loguru import logger
from config import LOGS_DIR
from ai_rpg.tui import GameClient
from ai_rpg.tui.config import server_config
from ai_rpg.tui.connecting import ConnectingScreen
from ai_rpg.tui.combat_room import CombatRoomScreen
from ai_rpg.tui.combat_post_combat import CombatPostCombatScreen
from textual.screen import Screen

# PyInstaller frozen bundle 检测：打包后 sys.frozen = True
_IS_FROZEN: bool = getattr(sys, "frozen", False)

# 默认服务器连接配置（可通过命令行参数覆盖）──
_DEFAULT_SERVER_HOST: Final[str] = "192.168.192.105"
_DEFAULT_SERVER_PORT: Final[int] = 8000

# ── loguru 配置：移除默认 stderr sink，改为文件输出（TUI 渲染期间不能写终端）──
logger.remove()
logger.add(
    LOGS_DIR / f"tui_client_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
    rotation="10 MB",
    # retention=3,
    level="DEBUG",
    encoding="utf-8",
)


@click.command()
@click.option(
    "--server-host",
    default=_DEFAULT_SERVER_HOST,
    show_default=True,
    help="游戏服务器地址",
)
@click.option(
    "--server-port",
    default=_DEFAULT_SERVER_PORT,
    show_default=True,
    help="游戏服务器端口",
)
@click.option(
    "--web",
    is_flag=True,
    default=False,
    help="以浏览器模式启动（通过 textual-serve 提供 Web 访问）",
)
@click.option("--port", default=8080, show_default=True, help="浏览器模式监听端口")
@click.option(
    "--host",
    default="localhost",
    show_default=True,
    help="浏览器模式监听地址（局域网用 0.0.0.0）",
)
@click.option(
    "--public-url",
    default=None,
    help="WebSocket 公开地址，局域网模式必填，例如 http://192.168.1.100:8080",
)
@click.option(
    "--dev-screen",
    type=click.Choice(["combat-room", "combat-post-combat"]),
    default=None,
    help="[开发用] 跳过登录流程，启动后直接进入指定页面（combat-room / combat-post-combat）",
)
def main(
    server_host: str,
    server_port: int,
    web: bool,
    port: int,
    host: str,
    public_url: Optional[str],
    dev_screen: Optional[str],
) -> None:
    server_config.host = server_host
    server_config.port = server_port

    if web:
        # frozen bundle 不含 textual-serve，拒绝 --web 模式
        if _IS_FROZEN:
            click.echo(
                "[错误] --web 模式在打包版本中不可用。\n"
                "请直接运行，TUI 将在当前终端窗口显示。"
            )
            sys.exit(1)

        command = (
            f"{sys.executable} {os.path.abspath(__file__)}"
            f" --server-host {server_host} --server-port {server_port}"
        )
        if dev_screen is not None:
            command += f" --dev-screen {dev_screen}"
        server = Server(command, host=host, port=port, public_url=public_url)
        display_url = public_url or f"http://{host}:{port}"
        click.echo(f"启动 Web 模式，请在浏览器打开: {display_url}")
        server.serve()
    else:

        # 分叉逻辑。
        launch_screen: Type[Screen[None]]
        if dev_screen == "combat-post-combat":
            launch_screen = CombatPostCombatScreen
        elif dev_screen == "combat-room":
            launch_screen = CombatRoomScreen
        else:
            launch_screen = ConnectingScreen

        # 启动 TUI 应用，传入选择的初始页面（launch_screen）
        app = GameClient(launch_screen=launch_screen)
        app.run()


if __name__ == "__main__":
    main()
