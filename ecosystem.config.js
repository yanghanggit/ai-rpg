module.exports = {
  apps: [
    // 游戏服务器实例 - 端口 8000
    {
      name: 'game-server-8000',
      script: 'uvicorn',
      args: 'scripts.run_game_server:app --host 0.0.0.0 --port 8000',
      interpreter: 'python',
      cwd: process.cwd(),
      env: {
        PYTHONPATH: `${process.cwd()}`,
        PORT: '8000'
      },
      instances: 1,
      autorestart: false,
      watch: false,
      max_memory_restart: '2G',
      log_file: './logs/game-server-8000.log',
      error_file: './logs/game-server-8000-error.log',
      out_file: './logs/game-server-8000-out.log',
      time: true
    }
  ]
};
