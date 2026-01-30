# AI-RPG

一个基于**多智能体架构**和**ECS (Entity Component System)** 的AI驱动型RPG游戏开发框架，深度集成大语言模型(LLM)实现动态内容生成和智能决策。

## ✨ 主要特性

- 🎮 **ECS架构**: 灵活的实体组件系统，支持复杂的游戏逻辑
- 🤖 **多智能体系统**: 每个角色、场景、世界系统拥有独立的AI上下文
- 🃏 **卡牌战斗系统**: TCG风格战斗，AI生成创意卡牌描述和战斗叙事
- 🏰 **地下城探索**: 多阶段副本系统，动态事件和敌人
- 📚 **RAG知识检索**: 基于向量数据库的语义搜索和知识增强
- 🎨 **AI内容生成**: 战斗描述、角色对话、场景叙事全部AI驱动
- ⚡ **Token优化**: 战斗系统压缩60%提示词，降低LLM成本
- 🔄 **世界持久化**: 完整的游戏状态保存和恢复机制

## 🛠️ 技术栈

### 核心框架

- **Python 3.12+**: 主要开发语言
- **FastAPI**: 高性能Web框架 (v0.116.1+)
- **Pydantic v2**: 数据验证和序列化

### AI与LLM

- **LangChain**: LLM编排框架 (v1.2.0+)
- **LangGraph**: 工作流编排 (v1.0.5+)
- **DeepSeek**: 主要AI模型 (chat + reasoner)
- **Sentence Transformers**: 文本向量化和语义搜索
- **OpenAI**: 备用LLM服务

### 数据存储

- **PostgreSQL**: 关系型数据库 (pgvector扩展)
- **ChromaDB**: 向量数据库，用于语义搜索和RAG

### 图像生成

- **Replicate**: 文本到图像生成API

### 开发工具

- **UV**: Python依赖管理工具
- **Black + Ruff**: 代码格式化和linting
- **MyPy**: 静态类型检查
- **Pytest**: 单元测试框架
- **Loguru**: 日志系统
- **OpenTelemetry**: 可观测性和监控

## 🚀 快速开始

### 环境要求

- Python 3.12+
- PostgreSQL (with pgvector extension)
- UV (Python包管理器)
- Make (可选，用于便捷命令)

### 安装步骤

#### 克隆项目

```bash
git clone <repository-url>
cd ai-rpg
```

#### 安装依赖

```bash
# 使用Makefile
make install

# 或直接使用UV
uv sync
```

#### 激活虚拟环境

```bash
# macOS/Linux
source .venv/bin/activate

# Windows
.\.venv\Scripts\activate
```

#### 配置环境变量

根据需要配置数据库连接、API密钥等环境变量。

### 启动方式

#### 方式1: 直接启动

```bash
# 启动游戏服务器
python scripts/run_game_server.py

# 启动DeepSeek聊天服务器
python scripts/run_deepseek_chat_server.py

# 启动图像生成服务
python scripts/run_replicate_image_server.py

# 运行终端演示游戏
python scripts/run_terminal_game.py
```

#### 方式2: 使用PM2（生产环境）

```bash
# 设置开发环境
python scripts/setup_dev_environment.py

# 使用PM2启动所有服务
pm2 start ecosystem.config.js
```

## 🏗️ 架构设计

### ECS (Entity Component System) 架构

```text
实体(Entity) = 组件(Component)的集合
  ├─ 角色(Actor): 玩家、NPC
  ├─ 场景(Stage): 村落、地下城
  └─ 世界系统(WorldSystem): 全局管理器

系统(System) 处理具有特定组件的实体
  ├─ KickOffSystem: 实体启动和初始化
  ├─ CombatInitializationSystem: 战斗初始化
  ├─ DrawCardsActionSystem: 卡牌生成
  ├─ ArbitrationActionSystem: 战斗仲裁
  └─ 其他23+个系统...
```

**核心文件**:

- ECS框架: `src/ai_rpg/entitas/`
- 游戏主类: `src/ai_rpg/game/rpg_game.py:1-834`
- 系统处理: `src/ai_rpg/systems/` (23个系统)

### 多智能体上下文管理

每个游戏实体拥有独立的 `AgentContext`，存储完整的对话历史：

```text
AgentContext消息结构:
[0] SystemMessage    ← 实体身份和规则（初始化，永不改变）
[1] HumanMessage     ← 游戏指令/事件
[2] AIMessage        ← LLM响应
[3] HumanMessage     ← 游戏通知（可连续）
...
```

**特性**:

- 多轮对话支持
- 系统提示词持久化
- 响应缓存机制
- 完整历史追溯

## 🎮 核心功能

### 卡牌战斗系统 (TCG)

完整的交易卡牌游戏战斗流程：

1. **战斗初始化**: 根据阵营关系生成初始状态效果
2. **卡牌生成**: AI创造性地生成卡牌名称和描述
3. **战斗仲裁**: 执行战斗计算，生成叙事文本
4. **战斗归档**: 保存战斗记录
5. **状态评估**: 评估并添加新的状态效果

**关键实现**:

- 战斗仲裁: `src/ai_rpg/systems/arbitration_action_system.py:1-632`
- 卡牌生成: `src/ai_rpg/systems/draw_cards_action_system.py:1-439`
- Token优化60%，降低LLM调用成本

### 地下城系统

- 多阶段副本探索
- 动态敌人生成
- 支持战斗/撤退选择
- 战利品和奖励系统

### RAG知识检索

- ChromaDB向量存储
- 语义搜索支持
- 游戏世界知识库
- 上下文增强生成

## 📁 项目结构

```text
src/ai_rpg/
├── entitas/              # ECS核心框架
│   ├── entity.py         # 实体基类
│   ├── context.py        # 实体管理器
│   ├── components.py     # 组件基类
│   └── processors.py     # 处理器框架
│
├── game/                 # 游戏核心逻辑
│   ├── rpg_game.py       # RPG游戏主类 (834行)
│   ├── rpg_entity_manager.py # 实体管理
│   ├── tcg_game.py       # 卡牌游戏扩展
│   ├── game_server.py    # 游戏服务器
│   └── world_persistence.py # 世界持久化
│
├── systems/              # ECS系统处理 (23个文件，5496行)
│   ├── kick_off_system.py
│   ├── combat_initialization_system.py
│   ├── draw_cards_action_system.py
│   ├── arbitration_action_system.py
│   └── ...
│
├── models/               # 数据模型
│   ├── entities.py       # 游戏实体
│   ├── components.py     # 组件定义
│   ├── actions.py        # 动作组件
│   └── dungeon.py        # 地下城数据结构
│
├── services/             # 业务逻辑服务
│   ├── deepseek_chat.py  # DeepSeek聊天服务
│   ├── home_gameplay.py  # 家园玩法
│   └── dungeon_gameplay.py # 地下城玩法
│
├── demo/                 # 演示内容
│   ├── world.py          # 演示世界蓝图
│   ├── global_settings.py # 全局设置
│   ├── prompt_templates.py # 提示词模板
│   └── dungeon_*.py      # 地下城副本
│
├── deepseek/             # DeepSeek LLM集成
├── rag/                  # RAG系统
├── chroma/               # ChromaDB集成
├── pgsql/                # PostgreSQL集成
└── auth/                 # 认证模块
```

## 🔧 开发指南

### 核心操作 (Makefile)

```bash
make install        # 安装所有依赖
make test          # 运行测试
make lint          # 代码检查
make format        # 代码格式化
make check-imports # 检查未使用的导入
```

### VS Code 配置

如果使用 VS Code + Anaconda 进行开发：

1. 打开命令面板 (`Cmd+Shift+P` / `Ctrl+Shift+P`)
2. 选择 `Python: Select Interpreter`
3. 选择 UV 环境路径：
   - macOS/Linux: `.venv/bin/python`
   - Windows: `.venv\Scripts\python.exe`

### Windows开发注意事项

1. 需要安装 **Git Bash**
2. 安装 Make 工具：

   ```bash
   winget install ezwinports.make
   ```

3. 确保选择正确的Python解释器：`.\.venv\Scripts\python.exe`

### 常见问题

**问题**: `a_request error: Server disconnected without sending a response`

**解决方案**: 检查VPN连接，尝试关闭VPN或使用WireGuard模式（Astrill VPN）。

## 📚 文档

详细文档位于 `docs/` 目录：

- 战斗系统架构
- 消息管理机制
- 提示词工程
- API文档

## 🎯 设计原则

1. **职责分离**: 系统间明确分工，各司其职
2. **数据单向流动**: 状态效果在特定阶段参与后"消失"
3. **Token优化**: 紧凑格式设计，降低LLM成本
4. **模块化**: 系统解耦，便于测试和复用
5. **类型安全**: 严格使用Pydantic和MyPy类型检查
6. **可观测性**: 完整的日志和监控支持

## 📊 项目统计

- **总代码量**: ~20,000+ 行
- **核心模块**: 132个Python文件
- **游戏系统**: 23个ECS系统处理器
- **数据模型**: 完整的Pydantic类型定义

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

[许可证信息]
