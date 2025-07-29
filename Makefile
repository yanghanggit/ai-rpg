.PHONY: install test lint format clean dev-install conda-install run-terminal run-server run-chat show-structure check test-mongodb start-mongodb stop-mongodb restart-mongodb status-mongodb mongo-shell help

# 安装包
install:
	pip install -e .

# 使用conda环境安装
conda-install:
	conda env update -f environment.yml
	conda run -n first_seed pip install -e .

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
	mypy --strict scripts/run_terminal_tcg_game.py scripts/run_tcg_game_server.py scripts/run_a_chat_server.py scripts/run_dev_clear_db.py scripts/get_dev_environment_info.py

# 格式化代码
format:
	black src/ tests/ scripts/

# 检查未使用的导入
check-imports:
	python scripts/check_unused_imports.py --check

# 修复未使用的导入
fix-imports:
	python scripts/check_unused_imports.py --fix

# 运行ruff检查（包含更多规则）
ruff-check:
	ruff check src/

# 运行ruff修复
ruff-fix:
	ruff check --fix src/

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

# 启动 MongoDB 服务
start-mongodb:
	brew services start mongodb/brew/mongodb-community

# 停止 MongoDB 服务
stop-mongodb:
	brew services stop mongodb/brew/mongodb-community

# 重启 MongoDB 服务
restart-mongodb:
	brew services restart mongodb/brew/mongodb-community

# 查看 MongoDB 状态
status-mongodb:
	brew services list | grep mongodb

# 连接到 MongoDB Shell
mongo-shell:
	mongosh

# 显示项目结构
show-structure:
	tree -I '__pycache__|*.pyc|*.pyo|*.pyd|*.so|.git|.pytest_cache|.mypy_cache' --dirsfirst

# 检查项目结构
check:
	@echo "检查项目目录结构..."
	@test -d src || echo "警告: src/ 目录不存在"
	@test -d tests || echo "警告: tests/ 目录不存在"
	@test -f requirements.txt || echo "警告: requirements.txt 文件不存在"
	@test -f pyproject.toml || echo "警告: pyproject.toml 文件不存在"
	@test -f environment.yml || echo "警告: environment.yml 文件不存在"
	@echo "项目结构检查完成"

# 显示所有可用的 make 目标
help:
	@echo "可用的命令:"
	@echo "  install        - 安装包"
	@echo "  conda-install  - 使用conda环境安装所有依赖"
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
	@echo "  test-mongodb   - 测试 MongoDB 连接和功能"
	@echo "  start-mongodb  - 启动 MongoDB 服务"
	@echo "  stop-mongodb   - 停止 MongoDB 服务"
	@echo "  restart-mongodb- 重启 MongoDB 服务"
	@echo "  status-mongodb - 查看 MongoDB 状态"
	@echo "  mongo-shell    - 连接到 MongoDB Shell"
	@echo "  help           - 显示此帮助信息"

.PHONY: install conda-install dev-install test lint format clean run-terminal run-server run-chat show-structure check test-mongodb start-mongodb stop-mongodb restart-mongodb status-mongodb mongo-shell help
