# First Seed

## 依赖包安装
```python
conda create -n first_seed python=3.10 

pip install langchain_core langserve fastapi langchain_openai sse_starlette faiss-cpu loguru mypy
```

## 注意点
- Agent运行的设备需要挂代理；

## 运行步骤

1. 先运行first_seed/agents下面的全部agent，启动agents服务器;
2. 然后运行main.py进行对话;

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
### 强制推送记忆(给NPC的chat history中加入输入的内容，但移除AI的回答)
- /push @npc_name>你现在需要xxx。

### 询问推理逻辑(询问NPC的推理逻辑,不会讲提问和AI的回答加入chat history)
- /ask @npc_name>为什么你没有xxx?


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






## yanghang gen npc test

pip install pandas openpyxl
