# multi-agents-game-framework

## 依赖包安装

```python
# 先安装anaconda或者miniconda

conda create -n Name python=3.12.2 

conda activate Name

pip install langchain langchain_core langserve langgraph fastapi langchain_openai sse_starlette faiss-cpu loguru mypy pandas openpyxl overrides Jinja2 jsonschema black pandas-stubs uvicorn

# Name 是环境的名，任取。
# 如果用vscode 进行代码调试，需要用 >Python Interpreter. 将python环境指向这个Name代表的环境
```

## 严格模式检查
- mypy --strict run_terminal_rpg_game.py run_rpg_game_server.py run_python_rpg_client.py batch_agent_app_launcher.py game_sample/gen_game.py game_sample/base_form_prompt_editor.py game_sample/actor_profile_prompt_editor.py game_sample/actor_conversational_style_prompt_editor.py game_sample/agentpy_templates/azure_chat_openai_gpt_4o_graph_base_template.py
- mypy --strict run_start_llm_serves.py run_test_llm_serve.py run_test_lang_serve_system.py

## 说明
- game_sample/gen_game.py 是生成游戏世界的配置
- batch_agent_app_launcher.py 可以批量启动agent
- run_terminal_rpg_game.py 利用终端启动游戏，方便调试
- run_rpg_game_server.py 启动一个服务器
- run_python_rpg_client.py 模拟一个网页客户端，与run_game_server.py进行交互。

## Windows平台运行问题
- agent的server代码报错：UnicodeEncodeError: 'gbk' codec can't encode character '\u26a0' in position 0: illegal multibyte sequence 
    - 在Windows的环境变量中加入 `PYTHONIOENCODING=utf-8`


## 升级langchain
- pip install --upgrade langchain langchain_core langserve langchain_openai langchain-community 
- pip show langchain langchain_core langserve langchain_openai langchain-community

## 自动化测试 (安装)
- conda install pytest

# Winsows平台使用WSL配置环境
## 安装WSL和Linux系统
可以follow[这篇文档](https://learn.microsoft.com/zh-cn/windows/wsl/install)
```shell
# 1.管理员身份运行CMD

# 2.安装wsl，运行：
wsl --install

# 3.安装系统，运行：
wsl --install -d Ubuntu-22.04

# 4.安装过程中配置用户名和密码
```
## 配置环境
### 安装Miniconda或Anaconda
```shell
# 下载安装包
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh

# 运行安装包(与安装包同路径下)
bash Miniconda3-latest-Linux-x86_64.sh
```
随后配置python环境的步骤同[前文](#依赖包安装)。
### 安装PM2
```shell
# 首先确保安装了Node.js和npm
node -v
npm -v

# 若未安装，运行以下命令安装
sudo apt update
sudo apt install nodejs npm

# 安装PM2
npm install -g pm2

# 检测安装是否成功
pm2 --version
```
### 安装git
```shell
sudo apt install git
git --version
```
### 安装zsh
```shell
# 安装
sudo apt-get install zsh

# 运行zsh，运行后按0退出，随后在.zshrc中配置key即可
zsh

# 程序首次运行前，需要在运行程序的shell中(即VScode的终端中)运行一次
source .zshrc
```
## 配置VScode
具体可以参考[官方文档](https://code.visualstudio.com/docs/remote/wsl)
1. 安装WSL插件
2. 把项目clone到虚拟环境中，open folder选择项目文件夹，随后点击弹窗中的```open in wsl```
3. 打开Extensions，在WSL环境中安装需要的插件，如Copilot，Python，Python Debugger，Pylance...