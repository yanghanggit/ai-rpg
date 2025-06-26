#!/bin/bash

# filepath: /Users/yanghang/Documents/GitHub/multi-agents-game-framework/chat_services/start_servers.sh

# 配置文件路径
CONFIG_FILE="$(dirname "$0")/chat_server_settings.json"

# 从 JSON 配置文件中读取参数
BASE_PORT=$(jq '.chat_service_base_port' "$CONFIG_FILE")
INSTANCES=$(jq '.num_chat_service_instances' "$CONFIG_FILE")

# 启动多个 uvicorn 实例
for ((i=0; i<INSTANCES; i++)); do
  PORT=$((BASE_PORT + i))
  echo "Starting server on port $PORT"
  uvicorn chat_services.chat_server_fastapi:app --host localhost --port $PORT &
done

echo "All servers started."