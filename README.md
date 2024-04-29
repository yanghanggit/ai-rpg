# First Seed

## 依赖包安装
```python
conda create -n first_seed python=3.10 

pip install langchain_core langserve fastapi langchain_openai sse_starlette faiss-cpu loguru mypy pandas openpyxl
```

## 注意点
- Agent运行的设备需要挂代理；

## 严格模式检查
- mypy --strict main.py

## 运行步骤
1. 进入`first_seed/budding_world/`文件夹，运行`python gen_budding_world.py`,输入世界名(budding_world.xlsx内的创建世界的sheet页名),输入版本号:`ewan`(目前builder的解析版本是ewan).
2. 运行`first_seed/budding_world/gen_agent`下面的全部agent，启动agents服务器;
3. 然后运行main.py进行对话,先输入第1步创建的世界名,然后可以输入`/run`推进世界进程。
4. 或者通过'/login'命令通过玩家身份登陆游戏游玩。

## “系统输入环节”的可用的命令, [system input]
```shell
# 退出游戏
/quit 
# 登陆游戏，目前是测试的名字与控制对象
/login
# 以GM的身份，世界运行一回合
/run
# 以GM的身份，强行向一个Agent发送Request，而且会加入chat history
/push
# 以GM的身份，强行向一个Agent发送Request，然后删除chat history，可以做调试用途（因为不会‘污染’逻辑上下文，例如用GM身份问的问题NPC会忘掉）
/ask
# 在登陆之后，可以用此命令切换身份，控制任意NPC
/who
```

## “玩家输入环节”的可用的命令
```shell
# 攻击目标NPC, 名字为Name?
/attack ‘Name?’
# 离开当前场景，去往Name?的场景
/leave ‘Name?’
# 在当前场景内广播内容。
/broadcast
# 对当前场景内的目标说话
/speak ‘@对谁>说话内容’
# 对当前场景内的目标低语
/whisper ‘@对谁>说话内容’
# 在当前场景内搜索叫‘Name?’的道具
/search ‘Name?’
# 在不知道去往哪里的情况下，‘跳出’当前场景，如果当前场景没有连接场景则会失败。
/prisonbreak
# 感知当前场景内有哪些人？事？道具？
/perception
# 盗取对当前场景内的目标的道具
/steal ‘@对谁>盗取的道具名字’
# 将我身上的道具交给目标
/trade ‘@对谁>我的道具的名字’
# 查看我身上有哪些道具？
/checkstatus
```

## World2的设计意图：
1. 过关条件：操作‘无名的复活者’，从‘埃利亚斯·格雷’身上获取‘断指钥匙’，并进入‘灰颜礼拜堂’
2. 初期需要离开‘禁言者之棺’。进入‘灰颜墓地’
3. 通过和‘埃利亚斯·格雷’的对话来逐步解锁更多信息和可以去的地方。
4. 如果发生敌意行为——玩家攻击‘埃利亚斯·格雷’意图夺取钥匙或偷盗被发现，‘摩尔’可能会发起攻击，‘摩尔’的目的就是测试一种‘保护者&随从’的类型。
4. ‘好运气先生’会根据场景情况，去惊醒‘鼠王’。这个主要是测试其推理与泛化能力。‘好运气先生’是‘条件触发者’的类型，只不过目前条件些的很隐晦。
5. ‘鼠王’如果被惊醒，就会在所有场景中寻找主角并攻击，玩家必死无疑。‘鼠王’是‘追击者’的类型。’鼠王‘苏醒就是变成‘鬼抓人’的游戏。
6. 唯一克制鼠王的办法是到‘焚化炉‘获取’炉钩‘。





