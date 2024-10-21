# multi-agents-game-framework

## 依赖包安装

```python
# 先安装anaconda或者miniconda

conda create -n Name python=3.12.2 

conda activate Name

pip install langchain langchain_core langserve fastapi langchain_openai sse_starlette faiss-cpu loguru mypy pandas openpyxl overrides Jinja2 jsonschema black

# Name 是环境的名字，任取。
# 如果用vscode 进行代码调试，需要用 >Python Interpreter. 将python环境指向这个Name代表的环境
```

## 严格模式检查
- mypy --strict game_sample/gen_game.py batch_run_agents.py terminal_run.py server_run.py web_run_simulate.py


### 说明

- terminal2.py 是通过终端进行访问测试游戏。默认会写死使用‘无名的复活者’这个测试的角色。
- game_sample/gen_game.py。是利用gameP_sample.xlsx来构建游戏世界的构建数据的程序（入口）

## 运行步骤

1. 进入`multi-agents-game-framework/game_sample/`文件夹，运行`python gen_game.py`,输入世界名(game_sample.xlsx内的创建世界的sheet页名, 如World2, World3),输入版本号:`0.0.1`(目前builder的解析版本是qwe). 附注：game_sample.xlsx 尽量每次都从飞书在线表格中下载，并覆盖multi-agents-game-framework/game_sample/excel/game_sample.xlsx，以保持最新。
2. 运行`multi-agents-game-framework/game_sample/gen_agent`下面的全部agent，启动agents服务器; 见下‘启动所有agents’
3. 然后运行terminal_run.py进行对话,先输入第1步创建的世界名(如World2？), 然后便可进行游戏。
4. 或者通过'/login'命令通过玩家身份登陆游戏游玩。

## 启动所有agents（方便复制粘贴）
可以直接调用 batch_run_agents.py来自动化运行（需要输入游戏名字, 例如，输入World2，就是执行'game_sample/gen_runtimes/World2_agents.json'）


# 可用指令
见 terminal2.py 的 add_player_command



### Windows平台运行问题

- agent的server代码报错：UnicodeEncodeError: 'gbk' codec can't encode character '\u26a0' in position 0: illegal multibyte sequence 
    - 在Windows的环境变量中加入 `PYTHONIOENCODING=utf-8`