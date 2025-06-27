#!/bin/bash

CONFIG_FILE="$(dirname "$0")/../server_settings.json"

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

# 函数：检查端口是否被占用
check_port() {
  local port=$1
  lsof -i :$port > /dev/null 2>&1
}

# 函数：终止占用指定端口的进程
kill_port() {
  local port=$1
  local pids=$(lsof -ti :$port)
  if [ -n "$pids" ]; then
    echo "端口 $port 被占用，终止进程: $pids"
    kill -9 $pids
    sleep 1
  fi
}

echo "检查并清理端口占用..."

# 清理所有需要使用的端口
for ((i=0; i<INSTANCES; i++)); do
  PORT=$((BASE_PORT + i))
  if check_port $PORT; then
    kill_port $PORT
  fi
done

# 清理旧的 PID 文件
PID_FILE="$(dirname "$0")/server_pids.txt"
if [ -f "$PID_FILE" ]; then
  echo "清理旧的 PID 文件: $PID_FILE"
  rm "$PID_FILE"
fi

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
