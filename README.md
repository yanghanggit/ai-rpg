# AI-RPG

一个基于**多智能体架构**和**ECS (Entity Component System)** 的AI驱动型RPG游戏开发框架，深度集成大语言模型(LLM)实现动态内容生成和智能决策。

## 🛠️ 技术栈

- **Python 3.12+** / **FastAPI** / **Pydantic v2**
- **DeepSeek** (chat + reasoner)
- **PostgreSQL** (pgvector)
- **Sentence Transformers** / **Replicate**（图像生成）
- **UV** / **Black** / **Ruff** / **MyPy** / **Pytest**

## 🚀 快速开始

### 环境要求

- Python 3.12+
- PostgreSQL（需启用 pgvector 扩展）
- [UV](https://github.com/astral-sh/uv)（Python 包管理器）

### 安装

```bash
git clone <repository-url>
cd ai-rpg

# 安装依赖
make install
# 或
uv sync

# 激活虚拟环境
source .venv/bin/activate        # macOS/Linux
# .\.venv\Scripts\activate       # Windows
```

配置数据库连接、API 密钥等环境变量后即可启动。

### 启动服务

各启动脚本见 `scripts/` 目录。使用 PM2 一键启动所有服务（生产环境）：

```bash
python -m scripts.setup_demo
pm2 start ecosystem.config.js
```

> AI 代理走查服务器 API 见 [scripts/run_agent_api.py](scripts/run_agent_api.py) 与 [docs/wiki/run-agent-api.md](docs/wiki/run-agent-api.md)（已取代原 TUI）。

## 📁 项目结构

```
ai-rpg/
├── src/ai_rpg/          # 包源码（src-layout；editable 安装为 `ai_rpg`）
│   ├── models/          #   Pydantic 模型（实体/组件/蓝图/战斗…）
│   ├── entitas/         #   ECS 框架
│   ├── game/            #   运行时 DBGGame、世界持久化
│   ├── services/        #   服务层 + FastAPI 路由（*_api.py）
│   ├── systems/         #   各类 ActionSystem
│   ├── game_agent/      #   快照驱动的离线推进（run_agent_game）
│   └── api_agent/       #   HTTP 走查封装（run_agent_api）
├── demo/                # 故事层（硬编码设定/蓝图），由 setup_demo 刷入配置与数据库
├── scripts/             # 入口脚本（run_game_server / run_agent_game / run_agent_api …）
├── tests/               # unit/ + integration/（pytest；统一 `from ai_rpg import ...`）
├── docs/                # 文档（docs/README.md 为根节点）
├── pyproject.toml       # 依赖与工具配置（[dependency-groups] dev、mypy_path=src、pytest pythonpath=src）
└── Makefile             # install / test / lint / check-imports
```

> 可导入代码统一放在 `src/`，经 editable 安装以 `ai_rpg` 暴露；测试、脚本、生产使用**同一导入身份**。

## 🔧 开发常用命令

```bash
make install        # uv sync（含 PEP 735 dev 依赖组），editable 安装本包
make test           # uv run pytest tests/ -v
make lint           # uv run mypy --strict src scripts tests demo
make check-imports  # ruff 检查未使用导入
make format         # black 格式化
```

更多见 `Makefile`。

> **Windows 用户**: 需要安装 [Git Bash](https://git-scm.com/) 和 Make（`winget install ezwinports.make`）。

## 📚 知识库

架构文档位于 `docs/`，以 [docs/README.md](docs/README.md) 为根节点。  
从根节点出发可导航至所有领域文档，适合在 Obsidian 中浏览（支持 Wiki 链接跳转）。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

[许可证信息]
