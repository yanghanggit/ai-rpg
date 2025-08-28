module.exports = {
  apps: [
    // 聊天服务器实例 - 端口 8100
    {
      name: 'azure-openai-chat-server-8100',
      script: 'uvicorn',
      args: 'scripts.run_azure_openai_chat_server:app --host 0.0.0.0 --port 8100',
      interpreter: 'python',
      cwd: process.cwd(),
      env: {
        PYTHONPATH: `${process.cwd()}`,
        PORT: '8100'
      },
      instances: 1,
      autorestart: false,
      watch: false,
      max_memory_restart: '2G',
      log_file: './logs/azure-openai-chat-server-8100.log',
      error_file: './logs/azure-openai-chat-server-8100-error.log',
      out_file: './logs/azure-openai-chat-server-8100-out.log',
      time: true
    },
    // 游戏服务器实例 - 端口 8000
    {
      name: 'game-server-8000',
      script: 'uvicorn',
      args: 'scripts.run_tcg_game_server:app --host 0.0.0.0 --port 8000',
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
