#!/bin/bash

SCRIPT_DIR="$(dirname "$0")"
CONFIG_FILE="$SCRIPT_DIR/../server_settings.json"
PID_FILE="$SCRIPT_DIR/../chat_servers.pid"

# 检查必要的工具和文件
if ! command -v jq &> /dev/null; then
    echo "错误: jq 未安装。请安装 jq 工具。"
    exit 1
fi

if ! command -v uvicorn &> /dev/null; then
    echo "错误: uvicorn 未找到。请确保已激活正确的 conda 环境。"
    exit 1
fi

if [ ! -f "$CONFIG_FILE" ]; then
    echo "错误: 配置文件未找到: $CONFIG_FILE"
    exit 1
fi

# 读取配置
BASE_PORT=$(jq '.chat_service_base_port' "$CONFIG_FILE")
INSTANCES=$(jq '.num_chat_service_instances' "$CONFIG_FILE")

if [ "$BASE_PORT" = "null" ] || [ "$INSTANCES" = "null" ]; then
    echo "错误: 配置文件格式错误或缺少必要字段"
    exit 1
fi

# 检查端口是否被占用
for ((i=0; i<INSTANCES; i++)); do
    PORT=$((BASE_PORT + i))
    if lsof -ti :$PORT &> /dev/null; then
        echo "错误: 端口 $PORT 已被占用。请先运行 kill_servers.sh 清理端口。"
        exit 1
    fi
done

# 清空之前的PID文件
> "$PID_FILE"

echo "启动聊天服务器..."

# 切换到项目根目录
cd "$SCRIPT_DIR/.."

# 启动所有服务器实例
for ((i=0; i<INSTANCES; i++)); do
    PORT=$((BASE_PORT + i))
    echo "启动服务器实例 $((i+1))/$INSTANCES，端口: $PORT"
    
    # 使用 PYTHONPATH 确保模块能被找到
    PYTHONPATH="$PWD/src:$PYTHONPATH" uvicorn multi_agents_game.chat_services.chat_server_fastapi:app --host localhost --port $PORT &
    SERVER_PID=$!
    echo $SERVER_PID >> "$PID_FILE"
    
    # 等待服务器启动并检查是否成功
    sleep 1
    if ! kill -0 $SERVER_PID 2>/dev/null; then
        echo "错误: 服务器实例 $((i+1)) 启动失败"
        exit 1
    fi
    
    echo "服务器实例 $((i+1)) 启动成功，PID: $SERVER_PID"
done

echo "所有服务器已启动完成."
echo "PID 文件: $PID_FILE"
echo "端口范围: $BASE_PORT-$((BASE_PORT + INSTANCES - 1))"
