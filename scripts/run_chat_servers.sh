#!/bin/bash

CONFIG_FILE="$(dirname "$0")/../server_settings.json"
BASE_PORT=$(jq '.chat_service_base_port' "$CONFIG_FILE")
INSTANCES=$(jq '.num_chat_service_instances' "$CONFIG_FILE")

echo "启动聊天服务器..."

# 启动所有服务器实例
for ((i=0; i<INSTANCES; i++)); do
  PORT=$((BASE_PORT + i))
  echo "Starting server on port $PORT"
  cd "$(dirname "$0")/.." && uvicorn multi_agents_game.chat_services.chat_server_fastapi:app --host localhost --port $PORT &
  echo $! >> "$PID_FILE"
  sleep 0.5  # 给服务器一点启动时间
done

echo "所有服务器已启动完成. PID 文件: $PID_FILE"
