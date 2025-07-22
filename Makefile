.PHONY: install test lint format clean dev-install run-terminal run-server run-chat show-structure check help

# 安装包
install:
	pip install -e .

# 安装开发依赖
dev-install:
	pip install -e ".[dev]"
	# 或者使用 requirements-dev.txt
	# pip install -r requirements-dev.txt

# 运行测试
test:
	pytest tests/ -v

# 运行类型检查
lint:
	mypy src/multi_agents_game/
	mypy --strict scripts/run_terminal_tcg_game.py scripts/run_tcg_game_server.py scripts/run_a_chat_server.py

# 格式化代码
format:
	black src/ tests/ scripts/

# 清理构建文件
clean:
	rm -rf build/ dist/ *.egg-info/
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete

# 运行终端游戏
run-terminal:
	python scripts/run_terminal_tcg_game.py

# 运行游戏服务器
run-server:
	python scripts/run_tcg_game_server.py

# 运行聊天服务器
run-chat:
	python scripts/run_a_chat_server.py

# 显示项目结构
show-structure:
	tree src/ -I "__pycache__"

# 检查项目结构
check:
	@echo "检查项目结构..."
	@ls -la src/multi_agents_game/
	@echo "检查配置文件..."
	@ls -la pyproject.toml requirements.txt

# 显示所有可用的 make 目标
help:
	@echo "可用的 make 目标："
	@echo "  install        - 安装项目包"
	@echo "  dev-install    - 安装开发依赖"
	@echo "  test           - 运行测试"
	@echo "  lint           - 运行类型检查"
	@echo "  format         - 格式化代码"
	@echo "  clean          - 清理构建文件"
	@echo "  run-terminal   - 运行终端游戏"
	@echo "  run-server     - 运行游戏服务器"
	@echo "  run-chat       - 运行聊天服务器"
	@echo "  show-structure - 显示项目结构"
	@echo "  check          - 检查项目结构"
	@echo "  help           - 显示此帮助信息"
