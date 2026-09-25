# AI-RPG

一个基于**多智能体架构**与 **ECS (Entity Component System)** 的 AI 驱动型 RPG 框架：
以 ECS 承载世界与规则，以 LLM（DeepSeek）驱动剧情、卡牌与战斗中的动态决策与内容生成。

> 正式玩家入口是独立仓库的 Web 客户端（`ai-rpg-web`）；本仓库是**引擎 + 常驻服务端 + 服务端真相**，
> 同时自带两个面向 AI 代理的命令行工具。

## 🛠️ 技术栈

- **Python 3.12+** / **FastAPI** / **Pydantic v2**
- **DeepSeek**（chat + reasoner）
- **PostgreSQL**（pgvector）
- **Sentence Transformers** / **Replicate**（图像生成）
- **uv** / **Black** / **Ruff** / **MyPy** / **Pytest**

## 🚀 快速开始

### 环境要求

- Python 3.12+
- PostgreSQL（启用 pgvector 扩展）
- [uv](https://github.com/astral-sh/uv)

### 安装

```bash
git clone <repository-url>
cd ai-rpg

make install        # 等价 uv sync（含 dev 依赖组）
# 或
uv sync

source .venv/bin/activate        # macOS/Linux
# .\.venv\Scripts\activate       # Windows
```

### 配置

复制 `cp .env.example .env`，填好数据库连接、`DEEPSEEK_API_KEY`、`GAME_SERVER_PORT` 等。

### 首次初始化演示数据

```bash
python -m scripts.setup_demo     # 把 demo/ 的硬编码设定刷入 .blueprints/ 与数据库
```

> `demo/` 在仓库根，故须**从项目根目录**以模块方式运行。

## ▶️ 启动与使用

### 启动游戏服务器

```bash
uv run ai-rpg-server                  # --port 缺省读 .env 的 GAME_SERVER_PORT
uv run ai-rpg-server --host 0.0.0.0 --port 8000

# 验证
curl http://127.0.0.1:8000/
```

生产环境用 PM2 托管：

```bash
pm2 start ecosystem.config.js
```

### 后台定时任务

服务器在 `lifespan` 内启动两个进程内定时循环（与 `GameServer` 同进程 / 同事件循环）：

| 环境变量 | 默认 | 说明 |
| --- | --- | --- |
| `GAME_ROOM_REAP_INTERVAL_SECONDS` | `60` | 空闲房间回收的扫描间隔 |
| `GAME_ROOM_TTL_SECONDS` | `1800` | 房间空闲多久后被回收；`<=0` 关闭回收 |
| `GAME_TICK_INTERVAL_SECONDS` | `60` | 游戏玩法定时器（`services/gameplay_scheduler.py`）的间隔；`<=0` 关闭 |

游戏玩法定时器目前仅为骨架（`on_room_tick` 为空实现），用于后续添加“定时查看 ECS 状态并触发玩法”的逻辑。

### 面向 AI 代理的工具（非人工操作）

游戏的「操作」由 AI 代理驱动，日常无需人手动执行。本仓库提供两条代理路径，
此处仅列入口，**用法、参数与环境变量见各自文档**：

| 命令 | 用途 | 文档 |
| --- | --- | --- |
| `ai-rpg-agent-game` | 离线、快照驱动推进（可回溯、可复现） | [docs/wiki/run-agent-game.md](docs/wiki/run-agent-game.md) |
| `ai-rpg-agent-api` | 通过 HTTP 走查服务器 API | [docs/wiki/run-agent-api.md](docs/wiki/run-agent-api.md) |

`uv run <命令> --help` 可列出全部子命令。

## 🔧 开发

```bash
make install        # uv sync（含 dev 依赖组）+ editable 安装
make test           # uv run pytest tests/ -v
make lint           # uv run mypy --strict + ruff check
make format         # black 格式化
```

### 测试约定

- 测试一律 `from ai_rpg... import ...`（**不要** `from src.ai_rpg...`）——测试、脚本、生产共用同一导入身份。
- `tests/` 不是包（无 `__init__.py`）；pytest 走 `--import-mode=importlib` + `pythonpath=["src"]`。
- 共享测试代码放包里（如 `src/ai_rpg/entitas/testing.py`）或 `tests/conftest.py` 的 fixture，不要 `from tests... import`。

> **Windows 用户**：需装 [Git Bash](https://git-scm.com/) 与 Make（`winget install ezwinports.make`）。

## 📚 文档

架构文档位于 `docs/`，以 [docs/README.md](docs/README.md) 为根节点。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

[许可证信息]
