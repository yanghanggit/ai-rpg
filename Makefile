.PHONY: install test lint format clean dev-install conda-install conda-setup check-imports fix-imports pip-install show-structure check help

# 默认目标：显示帮助信息
.DEFAULT_GOAL := help

# 推荐：Conda环境完整设置
conda-setup:
	@echo "🚀 设置Conda环境..."
	@if conda info --envs | grep -q first_seed; then \
		echo "⚠️  环境 first_seed 已存在，正在移除..."; \
		conda env remove -n first_seed -y; \
	fi
	conda env create -f environment.yml
	conda run -n first_seed pip install -e .
	@echo "✅ Conda环境设置完成！运行: conda activate first_seed"

# 更新现有conda环境
conda-install:
	@echo "🔄 更新Conda环境..."
	conda env update -f environment.yml --prune
	conda run -n first_seed pip install -e .
	@echo "✅ Conda环境更新完成！"

# 传统pip安装（备用方案）
pip-install:
	@echo "📦 使用pip安装依赖..."
	pip install -r requirements.txt
	pip install -e .
	@echo "✅ pip安装完成！"

# 简化的安装命令（默认使用conda）
install: conda-install

# 安装开发依赖（conda环境自动包含，pip环境需要额外安装）
dev-install:
	@if conda info --envs | grep -q first_seed; then \
		echo "✅ Conda环境已包含开发依赖"; \
	else \
		echo "📦 安装开发依赖..."; \
		pip install -r requirements-dev.txt; \
	fi

# 运行测试
test:
	pytest tests/ -v

# 运行类型检查（适配conda和pip环境）
lint:
	@echo "🔍 运行类型检查..."
	@echo "📁 检查 scripts/ 目录..."
	mypy --strict scripts/
	@echo "📁 检查 src/ 目录..."
	mypy --strict src/
	@echo "📁 检查 tests/ 目录..."
	mypy --strict tests/

# 格式化代码
format:
	black .

# 检查未使用的导入
check-imports:
	@echo "🔍 检查未使用的导入..."
	@if conda info --envs | grep -q first_seed; then \
		conda run -n first_seed python scripts/check_unused_imports.py --check; \
	else \
		python scripts/check_unused_imports.py --check; \
	fi

# 修复未使用的导入
fix-imports:
	@echo "🔧 修复未使用的导入..."
	@if conda info --envs | grep -q first_seed; then \
		conda run -n first_seed python scripts/check_unused_imports.py --fix; \
	else \
		python scripts/check_unused_imports.py --fix; \
	fi

# 清理构建文件
clean:
	rm -rf build/ dist/ *.egg-info/
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
	@test -f requirements.txt || echo "❌ 警告: requirements.txt 文件不存在"
	@test -f pyproject.toml || echo "❌ 警告: pyproject.toml 文件不存在"
	@test -f environment.yml || echo "❌ 警告: environment.yml 文件不存在"
	@echo "🔍 检查环境状态..."
	@if conda info --envs | grep -q first_seed; then \
		echo "✅ Conda环境 first_seed 存在"; \
		conda run -n first_seed pip check; \
	else \
		echo "⚠️  Conda环境 first_seed 不存在，建议运行: make conda-setup"; \
		pip check 2>/dev/null || echo "⚠️  当前pip环境可能有依赖问题"; \
	fi
	@echo "✅ 项目结构检查完成"

# 显示所有可用的 make 目标
help:
	@echo "🚀 多智能体游戏框架 - 可用命令:"
	@echo ""
	@echo "📦 环境设置:"
	@echo "  conda-setup    - 🌟 推荐：创建完整的conda环境"
	@echo "  conda-install  - 🔄 更新现有conda环境"
	@echo "  pip-install    - 📦 使用pip安装（备用方案）"
	@echo "  install        - 📦 默认安装（使用conda）"
	@echo "  dev-install    - 🔧 安装开发依赖"
	@echo ""
	@echo "🔍 代码质量:"
	@echo "  test           - 🧪 运行测试"
	@echo "  lint           - 🔍 运行类型检查"
	@echo "  format         - ✨ 格式化代码"
	@echo "  check-imports  - 🔍 检查未使用的导入"
	@echo "  fix-imports    - 🔧 修复未使用的导入"
	@echo ""
	@echo "🔧 开发工具:"
	@echo "  show-structure - 📁 显示项目结构"
	@echo "  check          - ✅ 检查项目和环境状态"
	@echo "  clean          - 🧹 清理构建文件"
	@echo "  help           - ❓ 显示此帮助信息"
	@echo ""
	@echo "💡 推荐工作流:"
	@echo "  1. make conda-setup  # 首次设置"
	@echo "  2. conda activate first_seed"
	@echo "  3. make check        # 验证环境"
	@echo "  4. make test         # 运行测试"
