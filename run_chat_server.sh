#!/bin/bash
# 注意端口 chat_service_api_port
uvicorn chat_services.chat_server:app --host localhost --port 8100 --reload