.PHONY: install test lint format clean dev-install uv-install show-structure check help

# 默认目标：显示帮助信息
.DEFAULT_GOAL := help

# 推荐：uv 环境完整设置
install:
	@echo "🚀 使用 uv 设置环境..."
	uv sync
	@echo "✅ 环境设置完成！"

# 安装生产依赖（不含 dev 组）
uv-install:
	@echo "📦 使用 uv 安装生产依赖..."
	uv sync --no-dev
	@echo "✅ 生产依赖安装完成！"

# 安装开发依赖
dev-install:
	@echo "🔧 使用 uv 安装开发依赖..."
	uv sync
	@echo "✅ 开发依赖安装完成！"

# 运行测试
test:
	uv run pytest tests/ -v

# 运行类型检查
# mypy_path="src"（见 pyproject.toml）让 ai_rpg 在 scripts/src/tests 下解析到同一路径，
# 因此可单次运行、共用 .mypy_cache（早期跨目录缓存冲突已消除）。
lint:
	@echo "🔍 运行类型检查..."
	uv run mypy --strict src scripts tests demo
	@echo "🔍 运行 ruff 检查..."
	uv run ruff check src scripts tests demo

# 格式化代码
format:
	uv run black .

# 清理构建文件
clean:
	rm -rf build/ dist/ *.egg-info/
	rm -rf .mypy_cache .pytest_cache .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

# 显示项目结构
show-structure:
	tree -I '__pycache__|*.pyc|*.pyo|*.pyd|*.so|.git|.pytest_cache|.mypy_cache' --dirsfirst

# 检查项目结构和环境
check:
	@echo "🔍 检查项目目录结构..."
	@test -d src || echo "❌ 警告: src/ 目录不存在"
	@test -d tests || echo "❌ 警告: tests/ 目录不存在"
	@test -f pyproject.toml || echo "❌ 警告: pyproject.toml 文件不存在"
	@test -f uv.lock || echo "❌ 警告: uv.lock 文件不存在"
	@echo "🔍 检查环境状态..."
	@echo "✅ 使用 uv 管理依赖"
	@uv pip check 2>/dev/null || echo "⚠️  依赖可能有问题，运行: uv sync"
	@echo "✅ 项目结构检查完成"

# 显示所有可用的 make 目标
help:
	@echo "🚀 多智能体游戏框架 - 可用命令（uv 版本）:"
	@echo ""
	@echo "📦 环境设置:"
	@echo "  install        - 🌟 推荐：安装所有依赖（包括开发）"
	@echo "  uv-install     - 📦 仅安装生产依赖"
	@echo "  dev-install    - 🔧 安装开发依赖"
	@echo ""
	@echo "🔍 代码质量:"
	@echo "  test           - 🧪 运行测试"
	@echo "  lint           - 🔍 mypy + ruff 检查"
	@echo "  format         - ✨ 格式化代码"
	@echo ""
	@echo "🔧 开发工具:"
	@echo "  show-structure - 📁 显示项目结构"
	@echo "  check          - ✅ 检查项目和环境状态"
	@echo "  clean          - 🧹 清理构建文件"
	@echo "  help           - ❓ 显示此帮助信息"
	@echo ""
	@echo "💡 推荐工作流:"
	@echo "  1. make install      # 安装所有依赖"
	@echo "  2. make check        # 验证环境"
	@echo "  3. make test         # 运行测试"
	@echo "  4. make lint         # 代码检查"
	@echo ""
	@echo "🚀 uv 常用命令:"
	@echo "  uv run python script.py   # 运行脚本"
	@echo "  uv add package-name        # 添加依赖"
	@echo "  uv remove package-name     # 移除依赖"
	@echo "  uv sync                    # 同步依赖"
