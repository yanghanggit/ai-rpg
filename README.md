# AI_RPG

一个基于多智能体架构的网络游戏开发框架，采用先进的提示词工程和上下文管理技术。

## 核心操作见 Makefile

- 如严格检查代码规范、运行测试、安装依赖等。

## 脚本见 `scripts/` 目录

- 如启动游戏服务器、运行测试等。

## VS Code 配置

如果使用 VS Code 进行开发 + 使用 Anaconda：

1. 打开命令面板 (`Cmd+Shift+P`)
2. 选择解释器 `Python: Select Interpreter`
3. 选择 uv 环境路径：`/.venv/Scripts/python.exe`

## 启动方式

1. 终端直接启动聊天服务器：在终端里运行`python scripts/run_deepseek_chat_server.py`
2. 使用pm2启动
    先运行`setup_dev_environment.py`
    在终端里运行`pm2 start ecosystem.config.js`

## Windows中的注意情况

1.需安装git bash。
2.使用UV后需安装Make工具 使用命令`winget install ezwinports.make`
3.注意python解释器，安装uv后选择    `.\.venv\Scripts\python.exe`

## 其他情况

如遇‘a_request error: Server disconnected without sending a response’ 检查vpn的情况，关掉vpn或者使用WireGuard（Astrill vpn）模式在重新运行。

## 激活uv环境

source .venv/bin/activate
