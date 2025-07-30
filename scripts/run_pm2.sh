#!/bin/bash
pm2 delete all
pm2 start scripts/run_chat_servers.sh scripts/run_tcg_game_server.py
