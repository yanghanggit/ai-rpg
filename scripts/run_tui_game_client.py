"""AI RPG 游戏客户端启动脚本（Textual TUI）

终端本地启动：
    uv run python scripts/run_tui_game_client.py

浏览器访问模式（供局域网/公网访问）：
    uv run python scripts/run_tui_game_client.py --web
    uv run python scripts/run_tui_game_client.py --web --port 8080
    然后在浏览器打开 http://localhost:8080

局域网模式（同事可通过你的 IP 访问）：
    # 先查询本机局域网 IP：
    ipconfig getifaddr en0           # 例如得到 192.168.1.100
    # 然后用实际 IP 启动（--public-url 告诉客户端用哪个地址连 WebSocket）：
    uv run python scripts/run_tui_game_client.py --web --host 0.0.0.0 --port 8080 --public-url http://192.168.1.100:8080
    # 同事浏览器打开 http://192.168.1.100:8080
"""

import sys
import os

import click

from ai_rpg.tui_client import GameClient

# PyInstaller frozen bundle 检测：打包后 sys.frozen = True
_IS_FROZEN: bool = getattr(sys, "frozen", False)


@click.command()
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
def main(web: bool, port: int, host: str, public_url: str | None) -> None:
    if web:
        # frozen bundle 不含 textual-serve，拒绝 --web 模式
        if _IS_FROZEN:
            click.echo(
                "[错误] --web 模式在打包版本中不可用。\n"
                "请直接运行，TUI 将在当前终端窗口显示。"
            )
            sys.exit(1)

        from textual_serve.server import Server

        command = f"{sys.executable} {os.path.abspath(__file__)}"
        server = Server(command, host=host, port=port, public_url=public_url)
        display_url = public_url or f"http://{host}:{port}"
        click.echo(f"启动 Web 模式，请在浏览器打开: {display_url}")
        server.serve()
    else:
        app = GameClient()
        app.run()


if __name__ == "__main__":
    main()
