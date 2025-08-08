module.exports = {
  apps: [
    // 游戏服务器 - 端口 8000
    {
      name: 'game-server-8000',
      script: 'scripts/run_tcg_game_server.py',
      interpreter: 'python',
      cwd: process.cwd(),
      env: {
        PYTHONPATH: `${process.cwd()}/src`
      },
      instances: 1,
      autorestart: false,
      watch: false,
      max_memory_restart: '2G',
      log_file: './logs/game-server.log',
      error_file: './logs/game-server-error.log',
      out_file: './logs/game-server-out.log',
      time: true
    },
    
    // 聊天服务器实例 1 - 端口 8100
    {
      name: 'chat-server-8100',
      script: 'uvicorn',
      args: 'multi_agents_game.chat_services.chat_server_fastapi:app --host 0.0.0.0 --port 8100',
      interpreter: 'python',
      cwd: process.cwd(),
      env: {
        PYTHONPATH: `${process.cwd()}/src`,
        PORT: '8100'
      },
      instances: 1,
      autorestart: false,
      watch: false,
      max_memory_restart: '2G',
      log_file: './logs/chat-server-8100.log',
      error_file: './logs/chat-server-8100-error.log',
      out_file: './logs/chat-server-8100-out.log',
      time: true
    },
    
    // 聊天服务器实例 2 - 端口 8101
    {
      name: 'chat-server-8101',
      script: 'uvicorn',
      args: 'multi_agents_game.chat_services.chat_server_fastapi:app --host 0.0.0.0 --port 8101',
      interpreter: 'python',
      cwd: process.cwd(),
      env: {
        PYTHONPATH: `${process.cwd()}/src`,
        PORT: '8101'
      },
      instances: 1,
      autorestart: false,
      watch: false,
      max_memory_restart: '2G',
      log_file: './logs/chat-server-8101.log',
      error_file: './logs/chat-server-8101-error.log',
      out_file: './logs/chat-server-8101-out.log',
      time: true
    },
    
    // 聊天服务器实例 3 - 端口 8102
    {
      name: 'chat-server-8102',
      script: 'uvicorn',
      args: 'multi_agents_game.chat_services.chat_server_fastapi:app --host 0.0.0.0 --port 8102',
      interpreter: 'python',
      cwd: process.cwd(),
      env: {
        PYTHONPATH: `${process.cwd()}/src`,
        PORT: '8102'
      },
      instances: 1,
      autorestart: false,
      watch: false,
      max_memory_restart: '2G',
      log_file: './logs/chat-server-8102.log',
      error_file: './logs/chat-server-8102-error.log',
      out_file: './logs/chat-server-8102-out.log',
      time: true
    }
  ]
};

/*
# 确保在项目根目录
cd /path/to/your/multi-agents-game-framework

# 启动所有服务
pm2 start ecosystem.config.js

# 查看状态
pm2 status

# 停止所有服务
pm2 delete ecosystem.config.js
*/
