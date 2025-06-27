#!/bin/bash

SCRIPT_DIR="$(dirname "$0")"
CONFIG_FILE="$SCRIPT_DIR/../server_settings.json"

# 函数：从 PID 文件终止进程
kill_from_pid_file() {
  local pid_file="$SCRIPT_DIR/server_pids.txt"
  if [ -f "$pid_file" ]; then
    echo "从 PID 文件终止服务器进程..."
    while read -r pid; do
      if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        echo "终止进程 PID: $pid"
        kill -9 "$pid"
      fi
    done < "$pid_file"
    rm "$pid_file"
    echo "PID 文件已清理"
  else
    echo "PID 文件未找到: $pid_file"
  fi
}

# 函数：从端口终止进程
kill_from_ports() {
  if [ -f "$CONFIG_FILE" ] && command -v jq &> /dev/null; then
    echo "从配置文件读取端口并终止相关进程..."
    local base_port=$(jq '.chat_service_base_port' "$CONFIG_FILE")
    local instances=$(jq '.num_chat_service_instances' "$CONFIG_FILE")
    local game_port=$(jq '.game_server_port' "$CONFIG_FILE")

    # 终止聊天服务器端口
    for ((i=0; i<instances; i++)); do
      local port=$((base_port + i))
      local pids=$(lsof -ti :$port 2>/dev/null)
      if [ -n "$pids" ]; then
        echo "终止端口 $port 上的进程: $pids"
        kill -9 $pids
      fi
    done

    # 终止游戏服务器端口
    local game_pids=$(lsof -ti :$game_port 2>/dev/null)
    if [ -n "$game_pids" ]; then
      echo "终止游戏服务器端口 $game_port 上的进程: $game_pids"
      kill -9 $game_pids
    fi
  else
    echo "配置文件未找到或 jq 未安装，跳过端口清理"
  fi
}

# 先尝试从 PID 文件终止
kill_from_pid_file

# 再从端口终止（确保清理干净）
kill_from_ports

echo "服务器终止完成"
