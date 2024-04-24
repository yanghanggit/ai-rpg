# First Seed

## 依赖包安装
```python
conda create -n first_seed python=3.10 

pip install langchain_core langserve fastapi langchain_openai sse_starlette faiss-cpu loguru mypy pandas openpyxl
```

## 注意点
- Agent运行的设备需要挂代理；

## 运行步骤
1. 进入`first_seed/budding_world/`文件夹，运行`python gen_budding_world.py`,输入世界名(budding_world.xlsx内的创建世界的sheet页名),输入版本号:`ewan`(目前builder的解析版本是ewan).
2. 运行`first_seed/budding_world/gen_agent`下面的全部agent，启动agents服务器;
3. 然后运行main.py进行对话,先输入第1步创建的世界名,然后输入`/run`开始对话.  

## 最小运行步骤
```shell
# 先运行初始化
/run
# 搜索进入小木屋的必要道具
/search '小木屋的钥匙'
# 进入小木屋
/leave 老猎人隐居的小木屋
# 执行推理一轮
/run
# 搜索进入地下城的必要道具
/search '古老的地图'
# 进入地下城
/leave 地下城
# 执行推理一轮
/run
# 搜索离开地下城的必要道具
/search '传说中的圣剑'
# 离开地下城前往悠扬林谷
/leave 悠扬林谷
# 执行推理一轮
/run
```

### 注意事项
- 由于当前'古老的地图'唯一且无道具转移机制，所以‘无名旅人’在进入小木屋拿到'古老的地图'前被其NPC先拿到则无法继续。

## 系统运行一回合
- /run

## 系统消息
### GM调试指令，发生了完整的request，同时对话结果会进入chat history。相当于强制给agent添加了一段“记忆”。
- /push @npc_name>你现在需要xxx。
- 结果：“npc_name”的NPC可能就会因为上下文的改变而改变策略，需要谨慎调用

### GM调试指令，发生了request，但是会移除本次chat history。相当于在不干扰"上下文"的基础上做了一次调试
- /ask @npc_name>为什么你没有xxx?
- 结果：“npc_name”的NPC，做一次回答之后，就会忘掉本次的对话，不会产生任何相关的后续策略与计划

## 控制npc
- /who 卡斯帕·艾伦德
- /who 断剑
- /who 坏运气先生
- /who 老猎人隐居的小木屋
- /who 悠扬林谷

### 攻击npc
- /attack 断剑'
- /attack 卡斯帕·艾伦德
- /attack 坏运气先生

### 离开场景
- /leave 老猎人隐居的小木屋
- /leave 悠扬林谷

### Broadcast
- /broadcast 大家好啊

### SpeakToNpc
- /speak @断剑>你是谁？

### WhisperToNpc
- /whisper @断剑>你喜欢吃什么？


## 严格模式检查
mypy --strict main.py

