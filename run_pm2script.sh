#!/bin/bash
./kill_servers.sh
pm2 delete all
pm2 start run_chat_servers.sh run_tcg_game_server.py