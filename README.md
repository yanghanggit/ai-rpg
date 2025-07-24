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

# 安装 pre-commit 钩子
pre-commit install

# 运行所有代码质量检查
pre-commit run --all-files
```

### 5. 快速启动服务器

使用独立脚本启动服务器：

```bash
# 启动聊天服务器
scripts/run_chat_servers.sh

# 启动游戏服务器
python scripts/run_tcg_game_server.py

# 停止所有服务器
scripts/kill_servers.sh
```

## 开发工具

### 严格模式检查

```shell
mypy --strict scripts/run_terminal_tcg_game.py scripts/run_tcg_game_server.py scripts/run_a_chat_server.py scripts/run_dev_clear_db.py

mypy --strict scripts/excel_write_test.py scripts/get_dev_environment_info.py
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

# 查看所有可用命令
make help

# 运行 pre-commit 检查（提交前推荐）
pre-commit run --all-files
```

### 服务器管理

#### 设置脚本执行权限

首次使用前，需要为脚本添加执行权限：

```shell
chmod +x scripts/run_chat_servers.sh
chmod +x scripts/kill_servers.sh
chmod +x scripts/run_pm2script.sh
```

#### 使用 Makefile（推荐方式）

```bash
# 启动单个服务
make run-chat      # 单个聊天服务器实例
make run-server    # 游戏服务器
make run-terminal  # 终端游戏
```

#### 直接使用脚本

```bash
# 独立脚本
scripts/run_chat_servers.sh             # 启动聊天服务器（自动清理端口）
python scripts/run_tcg_game_server.py   # 启动游戏服务器（自动清理端口）
python scripts/run_terminal_tcg_game.py # 启动终端游戏
scripts/kill_servers.sh                 # 停止所有服务器
```

#### 智能端口管理

所有服务器启动脚本现在都具备**智能端口清理功能**：

- **自动检测端口占用**：启动前检查配置的端口是否被占用
- **自动终止冲突进程**：如果端口被占用，自动终止相关进程
- **双重清理机制**：同时使用 PID 文件和端口检测确保彻底清理
- **状态监控**：提供实时的服务器运行状态查看

这意味着你再也不会遇到 "address already in use" 错误！

## 项目结构

```tree
multi-agents-game-framework/
├── src/multi_agents_game/          # 主包
│   ├── game/                       # 游戏核心逻辑
│   ├── models/                     # 数据模型
│   ├── tcg_game_systems/          # TCG 游戏系统
│   ├── chat_services/             # 聊天服务
│   ├── game_services/             # 游戏服务
│   ├── config/                    # 配置模块
│   ├── format_string/             # 字符串格式化工具
│   ├── chaos_engineering/         # 混沌工程
│   ├── player/                    # 玩家模块
│   └── entitas/                   # ECS 系统
├── scripts/                       # 运行脚本
│   ├── run_chat_servers.sh        # 聊天服务器启动脚本
│   ├── kill_servers.sh            # 服务器停止脚本
│   ├── run_tcg_game_server.py     # 游戏服务器启动脚本
│   └── run_terminal_tcg_game.py   # 终端游戏启动脚本
├── tests/                         # 测试文件
├── docs/                          # 文档
├── server_settings.json           # 服务器配置文件
├── environment.yml                # Conda 环境配置
├── pyproject.toml                 # 项目配置
├── Makefile                       # 构建和管理命令
├── mypy.ini                       # MyPy 类型检查配置
├── .pre-commit-config.yaml        # Pre-commit 钩子配置
└── README.md                      # 项目说明
```

## 主要功能

- **多智能体系统**: 基于 ECS (Entity-Component-System) 架构
- **TCG 游戏引擎**: 支持卡牌游戏逻辑和战斗系统
- **聊天服务**: 集成 AI 聊天功能，支持多实例部署
- **Web 服务**: FastAPI 驱动的游戏服务器
- **终端界面**: 支持终端模式的游戏交互
- **智能端口管理**: 自动检测和清理端口冲突，无需手动处理
- **统一配置管理**: 集中式配置文件管理所有服务器端口
- **类型安全**: 完整的 MyPy 类型检查支持

## 开发指南

### 代码质量规范

1. **代码风格**: 使用 Black 进行代码格式化
2. **类型检查**: 必须通过 MyPy 严格模式检查
3. **测试**: 新功能需要添加对应的测试用例
4. **文档**: 重要功能需要添加文档说明

### Pre-commit 钩子

项目配置了 pre-commit 钩子来自动检查代码质量：

#### 安装和设置

```bash
# pre-commit 已包含在 requirements-dev.txt 中
pip install -r requirements-dev.txt

# 安装 pre-commit 钩子（首次设置）
pre-commit install
```

#### 使用方式

```bash
# 手动运行所有检查（推荐在提交前执行）
pre-commit run --all-files

# 只检查暂存的文件
pre-commit run

# 跳过 pre-commit 检查（不推荐）
git commit -m "your message" --no-verify
```

#### 常见问题处理

如果遇到类似 `trailing-whitespace...Failed` 的错误：

1. **不要恐慌** - pre-commit 已自动修复了格式问题
2. **重新添加文件** - `git add .`
3. **重新提交** - `git commit -m "your message"`

这是正常的工作流程，确保代码质量一致性。

### 环境管理

#### 更新 environment.yml

当安装新的包后，需要更新 environment.yml 文件：

```bash
# 导出当前环境到 environment.yml
conda env export > environment.yml

# 或者只导出显式安装的包（推荐用于版本控制）
conda env export --from-history > environment-minimal.yml
```

#### 验证环境配置

```bash
# 验证当前环境
conda list

# 检查特定包
conda list | grep -E "(redis|jose|psycopg2|passlib|bcrypt)"
```

### windows中的注意情况

1.需安装git bash,使用git bash时需先定义conda安装路径，让git bash可以使用conda环境。
2.environment.yml 中的部分包需要更改安装版本号，其中ncurses不需要。
3.注意python解释器，安装conda环境后选择时需选择带有firstseed的conda环境

### 其他情况

如遇‘a_request error: Server disconnected without sending a response’ 检查vpn的情况，关掉vpn或者使用WireGuard（Astrill vpn）模式在重新运行。

## 许可证

[添加您的许可证信息]

## 贡献

欢迎提交 Issues 和 Pull Requests！

## 支持

如有问题，请创建 Issue 或联系项目维护者。
