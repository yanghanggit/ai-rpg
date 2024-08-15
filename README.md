# multi-agents-game-framework

## 依赖包安装

```python
# 先安装anaconda或者miniconda

conda create -n Name python=3.12.2 

conda activate Name

pip install langchain langchain_core langserve fastapi langchain_openai sse_starlette faiss-cpu loguru mypy pandas openpyxl overrides Jinja2 jsonschema

# Name 是环境的名字，任取。
# 如果用vscode 进行代码调试，需要用 >Python Interpreter. 将python环境指向这个Name代表的环境
```

## 代理

- Agent运行的设备需要挂代理；

## 严格模式检查

- mypy --strict terminal_run.py
- mypy --strict server_run.py
- mypy --strict game_sample/gen_game.py
- mypy --strict terminal_run.py game_sample/gen_game.py server_run.py batch_run_agents.py

### 说明

- terminal_run.py 是通过终端进行访问测试游戏。默认会写死使用‘无名的复活者’这个测试的角色。
- server_run.py 是使用测试网页进行游戏。必须开启ipv6
- game_sample/gen_game.py。是利用gameP_sample.xlsx来构建游戏世界的构建数据的程序（入口）

## 运行步骤

1. 进入`multi-agents-game-framework/game_sample/`文件夹，运行`python gen_game.py`,输入世界名(game_sample.xlsx内的创建世界的sheet页名, 如World2, World3),输入版本号:`qwe`(目前builder的解析版本是qwe). 附注：game_sample.xlsx 尽量每次都从飞书在线表格中下载，并覆盖multi-agents-game-framework/game_sample/excel/game_sample.xlsx，以保持最新。
2. 运行`multi-agents-game-framework/game_sample/gen_agent`下面的全部agent，启动agents服务器; 见下‘启动所有agents’
3. 然后运行terminal_run.py进行对话,先输入第1步创建的世界名(如World2？), 然后便可进行游戏。
4. 或者通过'/login'命令通过玩家身份登陆游戏游玩。

## 启动所有agents（方便复制粘贴）

```shell
# 以ubuntu/macOS下pm2为例

cd multi-agents-game-framework

pm2 start game_sample/gen_agent/coffin_of_the_silent_one_agent.py game_sample/gen_agent/gray_chapel_agent.py game_sample/gen_agent/nameless_resurrector_agent.py game_sample/gen_agent/rat_king_agent.py game_sample/gen_agent/elias_gray_agent.py game_sample/gen_agent/moore_dog_agent.py game_sample/gen_agent/papal_emissary_agent.py game_sample/gen_agent/the_incinerator_agent.py game_sample/gen_agent/gray_cemetery_agent.py game_sample/gen_agent/mr_lucky_agent.py game_sample/gen_agent/rancid_cellar_agent.py game_sample/gen_agent/square_front_of_cemetery_agent.py game_sample/gen_agent/world_system_appearance_builder_agent.py
```

### 也可以直接调用 batch_run_agents.py来自动化运行（需要输入游戏名字, 例如，输入World2，就是执行'game_sample/gen_runtimes/World2_agents.json'）


# 可用指令

```
# 退出游戏

/quit

# 创建游戏房间

/create

# 加入已经存在的房间

/join @'host_ip'

例如 /join @127.0.0.1

# 选择角色

/pickactor @'角色名称'

例如 /pickactor @无名的复活者

例如 /pickactor @教廷密使

# 对谁使用某个道具

/useprop @'对象名字'>'道具名称'

例如 /useprop @禁言铁棺>腐朽的匕首

# 攻击目标Actor, 名字为Name?

/attack '角色名称'

例如 /attack 摩尔

# 离开当前场景，去往Name?的场景

/goto '场景名称'

例如 /goto 灰颜墓地

# 在当前场景内广播内容。场景内所有Actor都能听见

/broadcast '说的内容'

例如 /broadcast 你们是谁？

# 对当前场景内的目标说话

/speak '@对谁>说话内容'

例如 /speak @格雷>我这是在哪？

# 对当前场景内的目标私语

/whisper '@对谁>说话内容'

例如 /whisper @摩尔>嘘，别吵。

# 在当前场景内搜索叫'Name?'的道具

/searchprop '道具名称'

例如 /searchprop 腐朽的匕首

# 在不知道去往哪里的情况下，'跳出'当前场景，如果当前场景没有连接场景则会失败。

/portalstep

# 感知当前场景内有哪些人？事？道具？

/perception

# 盗取对当前场景内的目标的道具

/stealprop '@对谁>盗取的道具名字'

例如 /stealprop @格雷>断指钥匙

# 将我身上的道具交给目标

/giveprop '@对谁>我的道具的名字'

例如 /giveprop @格雷>炉钩

# 查看我身上有哪些道具？

/checkstatus
```


### Windows平台运行问题

- agent的server代码报错：UnicodeEncodeError: 'gbk' codec can't encode character '\u26a0' in position 0: illegal multibyte sequence 
    - 在Windows的环境变量中加入 `PYTHONIOENCODING=utf-8`