# Multi-Agents Game Framework

一个基于多智能体系统的游戏框架。

## 核心操作见 Makefile

- 如严格检查代码规范、运行测试、安装依赖等。

## 脚本见 `scripts/` 目录

- 如启动游戏服务器、运行测试等。

## VS Code 配置

如果使用 VS Code 进行开发 + 使用 Anaconda：

1. 打开命令面板 (`Cmd+Shift+P`)
2. 选择 `Python: Select Interpreter`
3. 选择 conda 环境路径：`/Users/your-username/anaconda3/envs/first_seed/bin/python`

## MongoDB 数据库配置

项目使用 MongoDB 作为主要数据存储，用于保存游戏世界状态、玩家数据等。

## Windows中的注意情况

1.需安装git bash,使用git bash时需先定义conda安装路径，让git bash可以使用conda环境。
2.environment.yml 中的部分包需要更改安装版本号，其中ncurses不需要。
3.注意python解释器，安装conda环境后选择时需选择带有firstseed的conda环境

## 其他情况

如遇‘a_request error: Server disconnected without sending a response’ 检查vpn的情况，关掉vpn或者使用WireGuard（Astrill vpn）模式在重新运行。
