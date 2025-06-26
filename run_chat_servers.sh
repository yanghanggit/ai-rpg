#!/bin/bash

CONFIG_FILE="$(dirname "$0")/chat_server_settings.json"

# 检查 jq 是否安装
if ! command -v jq &> /dev/null; then
  echo "jq 未安装，请先安装 jq"
  exit 1
fi

# 检查配置文件是否存在
if [ ! -f "$CONFIG_FILE" ]; then
  echo "配置文件 $CONFIG_FILE 不存在"
  exit 1
fi

BASE_PORT=$(jq '.chat_service_base_port' "$CONFIG_FILE")
INSTANCES=$(jq '.num_chat_service_instances' "$CONFIG_FILE")

for ((i=0; i<INSTANCES; i++)); do
  PORT=$((BASE_PORT + i))
  echo "Starting server on port $PORT"
  uvicorn chat_services.chat_server_fastapi:app --host localhost --port $PORT &
  echo $! >> server_pids.txt
done

echo "All servers started. PID 文件: server_pids.txt"