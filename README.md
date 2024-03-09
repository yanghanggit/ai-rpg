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


## yanghang_dev.py
- yanghang的代码测试
- pm2 start agents/world_watcher_agent.py agents/old_hunters_cabin_agent.py agents/old_hunter_agent.py agents/old_hunters_dog_agent.py



## 系统消息
- /call @all 你是谁？跟我说说你
- /call @小狗'断剑' 你喜欢吃什么？
- /call @老猎人隐居的小木屋 周围有什么，你有什么布置？你自己最讨厌什么?
- /call @卡斯帕·艾伦德 最令你悔恨的是什么？
- /call @悠扬林谷 讲讲关于你
- /call @坏运气先生 你知道世界上的哪些地方？

## 创建玩家
- /createplayer 一个高大的兽人战士，独眼。手中拿着巨斧，杀气腾腾

## 要求场景做一次推进，最后必须加空格，因为解析没怎么写好
- /runstage 老猎人隐居的小木屋 

## 控制actor
- /who 卡斯帕·艾伦德
- /who 小狗'断剑'
- /who 坏运气先生
- /enterstage 老猎人隐居的小木屋
- /say2everyone 你们好呀！！
- /attack 卡斯帕·艾伦德
- /attack 坏运气先生
