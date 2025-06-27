#!/bin/bash

# 全服务器管理脚本
SCRIPT_DIR="$(dirname "$0")"

show_help() {
  echo "用法: $0 <命令>"
  echo "命令:"
  echo "  start-chat     启动聊天服务器"
  echo "  start-game     启动游戏服务器"
  echo "  start-all      启动所有服务器"
  echo "  stop           停止所有服务器"
  echo "  restart-chat   重启聊天服务器"
  echo "  restart-all    重启所有服务器"
  echo "  status         查看服务器状态"
  echo "  help           显示此帮助信息"
}

show_status() {
  CONFIG_FILE="$SCRIPT_DIR/../server_settings.json"
  if [ -f "$CONFIG_FILE" ] && command -v jq &> /dev/null; then
    local base_port=$(jq '.chat_service_base_port' "$CONFIG_FILE")
    local instances=$(jq '.num_chat_service_instances' "$CONFIG_FILE")
    local game_port=$(jq '.game_server_port' "$CONFIG_FILE")

    echo "=== 服务器状态 ==="
    echo "聊天服务器:"
    for ((i=0; i<instances; i++)); do
      local port=$((base_port + i))
      if lsof -i :$port > /dev/null 2>&1; then
        echo "  端口 $port: 运行中"
      else
        echo "  端口 $port: 未运行"
      fi
    done

    echo "游戏服务器:"
    if lsof -i :$game_port > /dev/null 2>&1; then
      echo "  端口 $game_port: 运行中"
    else
      echo "  端口 $game_port: 未运行"
    fi
  else
    echo "无法读取配置文件或 jq 未安装"
  fi
}

case "$1" in
  "start-chat")
    echo "启动聊天服务器..."
    "$SCRIPT_DIR/run_chat_servers.sh"
    ;;
  "start-game")
    echo "启动游戏服务器..."
    cd "$SCRIPT_DIR/.." && python scripts/run_tcg_game_server.py &
    ;;
  "start-all")
    echo "启动所有服务器..."
    "$SCRIPT_DIR/run_chat_servers.sh"
    sleep 2
    cd "$SCRIPT_DIR/.." && python scripts/run_tcg_game_server.py &
    ;;
  "stop")
    echo "停止所有服务器..."
    "$SCRIPT_DIR/kill_servers.sh"
    ;;
  "restart-chat")
    echo "重启聊天服务器..."
    "$SCRIPT_DIR/restart_chat_servers.sh"
    ;;
  "restart-all")
    echo "重启所有服务器..."
    "$SCRIPT_DIR/kill_servers.sh"
    sleep 1
    "$SCRIPT_DIR/run_chat_servers.sh"
    sleep 2
    cd "$SCRIPT_DIR/.." && python scripts/run_tcg_game_server.py &
    ;;
  "status")
    show_status
    ;;
  "help"|"-h"|"--help")
    show_help
    ;;
  *)
    echo "未知命令: $1"
    show_help
    exit 1
    ;;
esac
