# multi-agents-game-framework

## 依赖包安装

先安装anaconda或者miniconda。
Name 是环境的名（任取）。
如果用vscode 进行代码调试，需要用 >Python Interpreter. 将python环境指向这个Name代表的环境

```python
conda create -n Name python=3.12.2 
conda activate Name
pip install langchain langchain_core langserve langgraph fastapi langchain_openai sse_starlette faiss-cpu loguru mypy pandas openpyxl overrides Jinja2 jsonschema black pandas-stubs uvicorn
```

## 严格模式检查

```shell
mypy --strict run_terminal_tcg_game.py run_tcg_game_server.py run_a_chat_server.py
```

## 注意添加权限

```shell
chmod +x run_chat_servers.sh
chmod +x run_pm2script.sh
```

## 升级langchain

```shell
pip install --upgrade langchain langchain_core langserve langchain_openai langchain-community 
pip show langchain langchain_core langserve langchain_openai langchain-community
```

## 自动化测试 (安装)

```shell
conda install pytest
```
