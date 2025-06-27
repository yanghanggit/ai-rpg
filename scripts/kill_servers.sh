#!/bin/bash

SCRIPT_DIR="$(dirname "$0")"
if [ -f "$SCRIPT_DIR/server_pids.txt" ]; then
    xargs kill < "$SCRIPT_DIR/server_pids.txt"
    rm "$SCRIPT_DIR/server_pids.txt"
    echo "Servers killed and PID file removed"
else
    echo "PID file not found: $SCRIPT_DIR/server_pids.txt"
fi
