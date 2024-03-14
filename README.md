# First Seed

## 依赖包安装
```python
conda create -n first_seed python=3.10 

pip install langchain_core langserve fastapi langchain_openai sse_starlette faiss-cpu
```

## 注意点
- Agent需要挂代理；

## 运行步骤

1. 先运行first_seed/agents下面的全部agent，启动agents服务器;
2. 然后运行main.py进行对话;


## yanghang的代码测试
- pm2 start agents/world_watcher_agent.py agents/old_hunters_cabin_agent.py agents/old_hunter_agent.py agents/old_hunters_dog_agent.py agents/rat_agent.py agents/melodious_forest_valley_agent.py agents/thief_agent.py



## 系统消息
- /call @all 你是谁？跟我说说你，并且告诉我你在做什么？
- /call @小狗'断剑' 你喜欢吃什么？
- /call @老猎人隐居的小木屋 周围有什么，你有什么布置？你自己最讨厌什么?
- /call @卡斯帕·艾伦德 最令你悔恨的是什么？
- /call @悠扬林谷 讲讲关于你
- /call @坏运气先生 你知道世界上的哪些地方？

## 创建玩家
- /player yanghang|老猎人隐居的小木屋|他是一个高大的兽人战士，独眼。手中拿着巨斧，杀气腾腾

## 控制npc
- /who 卡斯帕·艾伦德
- /who 小狗'断剑'
- /who 坏运气先生
- /who 老猎人隐居的小木屋
- /who 悠扬林谷

- /attack 小狗'断剑'
- /attack 卡斯帕·艾伦德
- /attack 坏运气先生