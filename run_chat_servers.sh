#!/bin/bash
# filepath: /Users/yanghang/Documents/GitHub/multi-agents-game-framework/start_servers.sh
# 注意和 chat_services/chat_server_config.py 一致。
# 定义起始端口和实例数量
start_port=8100
instances=3

for ((i=0; i<$instances; i++)); do
  port=$((start_port + i))
  echo "Starting server on port $port"
  uvicorn chat_services.chat_server:app --host localhost --port $port --reload &
done

echo "All servers started."