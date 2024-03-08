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