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
    },
    // 图片生成服务器实例 - 端口 8300
    {
      name: 'image-generation-server-8300',
      script: 'uvicorn',
      args: 'scripts.run_replicate_image_server:app --host 0.0.0.0 --port 8300',
      interpreter: 'python',
      cwd: process.cwd(),
      env: {
        PYTHONPATH: `${process.cwd()}`,
        PORT: '8300'
      },
      instances: 1,
      autorestart: false,
      watch: false,
      max_memory_restart: '2G',
      log_file: './logs/image-generation-server-8300.log',
      error_file: './logs/image-generation-server-8300-error.log',
      out_file: './logs/image-generation-server-8300-out.log',
      time: true
    },
    // DeepSeek聊天服务器实例 - 端口 8200
    {
      name: 'deepseek-chat-server-8200',
      script: 'uvicorn',
      args: 'scripts.run_deepseek_chat_server:app --host 0.0.0.0 --port 8200',
      interpreter: 'python',
      cwd: process.cwd(),
      env: {
        PYTHONPATH: `${process.cwd()}`,
        PORT: '8200'
      },
      instances: 1,
      autorestart: false,
      watch: false,
      max_memory_restart: '2G',
      log_file: './logs/deepseek-chat-server-8200.log',
      error_file: './logs/deepseek-chat-server-8200-error.log',
      out_file: './logs/deepseek-chat-server-8200-out.log',
      time: true
    }
  ]
};
