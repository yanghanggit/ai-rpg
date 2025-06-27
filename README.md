# Multi-Agents Game Framework

一个基于多智能体系统的游戏框架，支持 TCG（Trading Card Game）游戏开发，集成了聊天服务、游戏逻辑处理和 Web 服务等功能。

## 环境要求

- **Python**: 3.12.2
- **包管理器**: Conda (必须使用 Conda)

## 快速开始

### 1. 环境安装

**推荐使用 Conda 来管理环境**，支持多种安装方式：

#### 方式一：使用 environment.yml（推荐）

```bash
# 克隆项目
git clone <repository-url>
cd multi-agents-game-framework

# 使用 environment.yml 创建 conda 环境
conda env create -f environment.yml

# 激活环境
conda activate first_seed

# 安装项目包（开发模式）
pip install -e .
```

#### 方式二：使用 pyproject.toml

```bash
# 创建新的 conda 环境
conda create -n multi-agents-game python=3.12.2
conda activate multi-agents-game

# 安装项目及其依赖
pip install -e .

# 安装开发依赖
pip install -e ".[dev]"
```

#### 方式三：使用 requirements.txt

```bash
# 创建新的 conda 环境
conda create -n multi-agents-game python=3.12.2
conda activate multi-agents-game

# 安装依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 安装项目包
pip install -e .
```

### 2. VS Code 配置

如果使用 VS Code 进行开发：

1. 打开命令面板 (`Cmd+Shift+P`)
2. 选择 `Python: Select Interpreter`
3. 选择 conda 环境路径：`/Users/your-username/anaconda3/envs/first_seed/bin/python`

### 3. 配置服务器设置

项目使用 `server_settings.json` 文件来配置服务器端口：

```json
{
  "chat_service_base_port": 8100,
  "num_chat_service_instances": 1,
  "game_server_port": 8000
}
```

- `chat_service_base_port`: 聊天服务器基础端口
- `num_chat_service_instances`: 聊天服务器实例数量
- `game_server_port`: 游戏服务器端口

### 4. 验证安装

```bash
# 运行测试
pytest tests/ -v

# 检查类型
make lint

# 格式化代码
make format
```

## 开发工具

### 严格模式检查

```shell
mypy --strict scripts/run_terminal_tcg_game.py scripts/run_tcg_game_server.py scripts/run_a_chat_server.py
```

### 代码质量检查

```bash
# 类型检查
make lint

# 代码格式化
make format

# 运行所有测试
make test

# 清理构建文件
make clean
```

### 服务器管理

设置脚本执行权限：

```shell
chmod +x scripts/run_chat_servers.sh
chmod +x scripts/run_pm2script.sh
chmod +x scripts/kill_servers.sh
```

启动服务：

```bash
# 启动聊天服务器
scripts/run_chat_servers.sh

# 启动游戏服务器
python scripts/run_tcg_game_server.py

# 启动终端游戏
python scripts/run_terminal_tcg_game.py

# 停止所有服务器
scripts/kill_servers.sh
```

## 项目结构

```tree
multi-agents-game-framework/
├── src/multi_agents_game/          # 主包
│   ├── game/                       # 游戏核心逻辑
│   ├── models/                     # 数据模型
│   ├── tcg_game_systems/          # TCG 游戏系统
│   ├── chat_services/             # 聊天服务
│   ├── game_services/             # 游戏服务
│   ├── format_string/             # 字符串格式化工具
│   ├── chaos_engineering/         # 混沌工程
│   ├── player/                    # 玩家模块
│   └── entitas/                   # ECS 系统
├── scripts/                       # 运行脚本
├── tests/                         # 测试文件
├── docs/                          # 文档
├── environment.yml                # Conda 环境配置
├── pyproject.toml                 # 项目配置
└── README.md                      # 项目说明
```

## 主要功能

- **多智能体系统**: 基于 ECS (Entity-Component-System) 架构
- **TCG 游戏引擎**: 支持卡牌游戏逻辑和战斗系统
- **聊天服务**: 集成 AI 聊天功能，支持多实例部署
- **Web 服务**: FastAPI 驱动的游戏服务器
- **终端界面**: 支持终端模式的游戏交互
- **类型安全**: 完整的 MyPy 类型检查支持

## 依赖包更新

更新核心依赖包：

```shell
pip install --upgrade langchain langchain_core langserve langchain_openai langchain-community
pip show langchain langchain_core langserve langchain_openai langchain-community
```

## 开发指南

1. **代码风格**: 使用 Black 进行代码格式化
2. **类型检查**: 必须通过 MyPy 严格模式检查
3. **测试**: 新功能需要添加对应的测试用例
4. **文档**: 重要功能需要添加文档说明

## 许可证

[添加您的许可证信息]

## 贡献

欢迎提交 Issues 和 Pull Requests！

## 支持

如有问题，请创建 Issue 或联系项目维护者。
