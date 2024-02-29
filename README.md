# First Seed

## 运行步骤

1. 先运行两个agent脚本启动agent服务区；
2. 然后运行main.py进行对话；

## 依赖包安装
```python
conda create -n first_seed python=3.10 

pip install langchain_core langserve fastapi langchain_openai sse_starlette 
```

## 代理需求
- Agent需要挂代理；