module.exports = {
  apps: [
    // 聊天服务器实例 1 - 端口 8100
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
    }
  ]
};

/*
# 确保在项目根目录

# 启动所有服务
pm2 start ecosystem.config.js

# 查看状态
pm2 status

# 停止所有服务
pm2 delete ecosystem.config.js
*/
