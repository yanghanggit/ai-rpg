#!/usr/bin/env python3
"""
生成 PM2 进程管理配置文件 (ecosystem.config.js)

使用方式：
    python scripts/generate_pm2_config.py

Author: yanghanggit
Date: 2025-07-30
"""

import os
import sys
from pathlib import Path

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

# from ai_rpg.services import server_configuration
from config import GAME_SERVER_PORT


def main(target_directory: str = ".") -> None:
    """
    生成 PM2 进程管理配置文件

    Args:
        server_config: 服务器配置对象
        target_directory: 目标目录路径，默认为当前目录
    """
    ecosystem_config_content = f"""module.exports = {{
  apps: [
    // 游戏服务器实例 - 端口 {GAME_SERVER_PORT}
    {{
      name: 'game-server-{GAME_SERVER_PORT}',
      script: 'uvicorn',
      args: 'scripts.run_game_server:app --host 0.0.0.0 --port {GAME_SERVER_PORT}',
      interpreter: 'python',
      cwd: process.cwd(),
      env: {{
        PYTHONPATH: `${{process.cwd()}}`,
        PORT: '{GAME_SERVER_PORT}'
      }},
      instances: 1,
      autorestart: false,
      watch: false,
      max_memory_restart: '2G',
      log_file: './logs/game-server-{GAME_SERVER_PORT}.log',
      error_file: './logs/game-server-{GAME_SERVER_PORT}-error.log',
      out_file: './logs/game-server-{GAME_SERVER_PORT}-out.log',
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
