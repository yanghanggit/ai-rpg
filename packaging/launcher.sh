#!/usr/bin/env bash
# packaging/launcher.sh
#
# macOS .app launcher：双击后在新 Terminal 窗口里打开 TUI
#
# 本脚本位于 AI-RPG-Client.app/Contents/MacOS/AI-RPG-Client
# game_client 二进制位于同目录下

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BINARY="$SCRIPT_DIR/game_client"

# 通过 osascript 开一个新 Terminal 窗口运行 TUI（运行结束后窗口保持）
osascript <<EOF
tell application "Terminal"
    activate
    do script "$BINARY"
end tell
EOF
