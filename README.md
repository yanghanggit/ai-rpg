# First Seed

## 依赖包安装

```python
conda create -n first_seed python=3.12.2 

pip install langchain langchain_core langserve fastapi langchain_openai sse_starlette faiss-cpu loguru mypy pandas openpyxl overrides Jinja2
```

## 注意点

- Agent运行的设备需要挂代理；

## 严格模式检查

- mypy --strict terminal_run.py
- mypy --strict server.py
- mypy --strict budding_world/gen_game.py

### 说明

- terminal_run.py 是通过终端进行访问测试游戏。默认会写死使用‘无名的复活者’这个测试的角色。
- server.py 是使用测试网页进行游戏。
- budding_world/gen_game.py。是利用budding_world.xlsx来构建游戏世界的构建数据的程序（入口）

## 运行步骤

1. 进入`first_seed/budding_world/`文件夹，运行`python gen_game.py`,输入世界名(budding_world.xlsx内的创建世界的sheet页名, 如World2, World3),输入版本号:`ewan`(目前builder的解析版本是ewan). 附注：budding_world.xlsx 尽量每次都从飞书在线表格中下载，并覆盖first_seed/budding_world/settings_editor/budding_world.xlsx，以保持最新。
2. 运行`first_seed/budding_world/gen_agent`下面的全部agent，启动agents服务器; 见下‘启动所有agents’
3. 然后运行terminal_run.py进行对话,先输入第1步创建的世界名(如World2？), 然后便可进行游戏。
4. 或者通过'/login'命令通过玩家身份登陆游戏游玩。

## 启动所有agents（方便复制粘贴）

```shell
# 以ubuntu/macOS下pm2为例

cd first_seed

pm2 start budding_world/gen_agent/coffin_of_the_silent_one_agent.py budding_world/gen_agent/gray_chapel_agent.py budding_world/gen_agent/nameless_resurrector_agent.py budding_world/gen_agent/rat_king_agent.py budding_world/gen_agent/elias_gray_agent.py budding_world/gen_agent/moore_dog_agent.py budding_world/gen_agent/papal_emissary_agent.py budding_world/gen_agent/the_incinerator_agent.py budding_world/gen_agent/gray_cemetery_agent.py budding_world/gen_agent/mr_lucky_agent.py budding_world/gen_agent/rancid_cellar_agent.py budding_world/gen_agent/square_front_of_cemetery_agent.py
```

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

# 对当前场景内的目标低语

/whisper '@对谁>说话内容'

例如 /whisper @摩尔>嘘，别吵。

# 在当前场景内搜索叫'Name?'的道具

/search '道具名称'

例如 /search 腐朽的匕首

# 在不知道去往哪里的情况下，'跳出'当前场景，如果当前场景没有连接场景则会失败。

/portalstep

# 感知当前场景内有哪些人？事？道具？

/perception

# 盗取对当前场景内的目标的道具

/steal '@对谁>盗取的道具名字'

例如 /steal @格雷>断指钥匙

# 将我身上的道具交给目标

/trade '@对谁>我的道具的名字'

例如 /trade @格雷>炉钩

# 查看我身上有哪些道具？

/checkstatus
```
