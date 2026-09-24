#!/usr/bin/env python3
"""生成 ecosystem.config.js，启动游戏服务器（uvicorn）。"""


import os
from pathlib import Path

from dotenv import load_dotenv

# from ai_rpg.services import server_configuration

load_dotenv()


def main(target_directory: str = ".") -> None:
    """
    生成 PM2 进程管理配置文件
    """
    game_server_port_env = os.getenv("GAME_SERVER_PORT")
    if not game_server_port_env:
        raise RuntimeError(
            "环境变量 GAME_SERVER_PORT 未设置，请在 .env 中配置（参考 .env.example）"
        )
    game_server_port = int(game_server_port_env)
    ecosystem_config_content = f"""const path = require('path');

module.exports = {{
  apps: [
    // 游戏服务器实例 - 端口 {game_server_port}
    {{
      name: 'game-server-{game_server_port}',
      script: path.join(__dirname, '.venv/bin/uvicorn'),
      interpreter: 'none',
      args: 'ai_rpg.cli.server:app --host 0.0.0.0 --port {game_server_port}',
      cwd: __dirname,
      env: {{
        PYTHONPATH: `${{__dirname}}/src:${{__dirname}}`,
        PORT: '{game_server_port}'
      }},
      instances: 1,
      autorestart: false,
      watch: false,
      max_memory_restart: '2G',
      log_file: './logs/game-server-{game_server_port}.log',
      error_file: './logs/game-server-{game_server_port}-error.log',
      out_file: './logs/game-server-{game_server_port}-out.log',
      time: true
    }}
  ]
}};
"""
    target_path = Path(target_directory)
    target_path.mkdir(parents=True, exist_ok=True)

    config_file_path = target_path / "ecosystem.config.js"
    config_file_path.write_text(ecosystem_config_content, encoding="utf-8")

    print(f"已生成 ecosystem.config.js 文件到: {config_file_path.absolute()}")


if __name__ == "__main__":
    main()
