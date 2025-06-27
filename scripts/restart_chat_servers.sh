#!/bin/bash

# 重启聊天服务器脚本
echo "===== 重启聊天服务器 ====="

SCRIPT_DIR="$(dirname "$0")"

# 1. 先终止所有现有服务器
echo "1. 终止现有服务器..."
"$SCRIPT_DIR/kill_servers.sh"

# 等待一秒确保进程完全终止
sleep 1

# 2. 启动新的服务器
echo "2. 启动新的服务器..."
"$SCRIPT_DIR/run_chat_servers.sh"

echo "===== 重启完成 ====="
