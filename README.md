# multi-agents-game-framework

## 依赖包安装

```python
# 先安装anaconda或者miniconda

conda create -n Name python=3.12.2 

conda activate Name

pip install langchain langchain_core langserve fastapi langchain_openai sse_starlette faiss-cpu loguru mypy pandas openpyxl overrides Jinja2 jsonschema black

# Name 是环境的名，任取。
# 如果用vscode 进行代码调试，需要用 >Python Interpreter. 将python环境指向这个Name代表的环境
```

## 严格模式检查
- mypy --strict game_sample/gen_game.py batch_run_agents.py run_terminal_game.py run_game_server.py simulate_web_client.py game_sample/base_form_prompt_editor.py game_sample/actor_profile_prompt_editor.py game_sample/actor_conversational_style_prompt_editor.py


## 说明
- game_sample/gen_game.py 是生成游戏世界的配置
- batch_run_agents.py 可以批量启动agent
- run_terminal_game.py 利用终端启动游戏，方便调试
- server_run.py 启动一个服务器
- simulate_web_client.py 模拟一个网页客户端，与run_game_server.py进行交互。

## Windows平台运行问题

- agent的server代码报错：UnicodeEncodeError: 'gbk' codec can't encode character '\u26a0' in position 0: illegal multibyte sequence 
    - 在Windows的环境变量中加入 `PYTHONIOENCODING=utf-8`