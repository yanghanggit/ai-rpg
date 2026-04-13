# AI-RPG

一个基于**多智能体架构**和**ECS (Entity Component System)** 的AI驱动型RPG游戏开发框架，深度集成大语言模型(LLM)实现动态内容生成和智能决策。

## 🛠️ 技术栈

- **Python 3.12+** / **FastAPI** / **Pydantic v2**
- **LangChain** / **LangGraph** / **DeepSeek** (chat + reasoner)
- **PostgreSQL** (pgvector) / **ChromaDB**
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
python scripts/setup_dev_environment.py
pm2 start ecosystem.config.js
```

## 🔧 开发常用命令

见 `Makefile`。

> **Windows 用户**: 需要安装 [Git Bash](https://git-scm.com/) 和 Make（`winget install ezwinports.make`）。

## 📚 知识库

架构文档位于 `docs/`，以 [docs/README.md](docs/README.md) 为根节点。  
从根节点出发可导航至所有领域文档，适合在 Obsidian 中浏览（支持 Wiki 链接跳转）。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

[许可证信息]
