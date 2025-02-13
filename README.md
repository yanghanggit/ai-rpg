# multi-agents-game-framework

## 依赖包安装

```python
# 先安装anaconda或者miniconda

conda create -n Name python=3.12.2 

conda activate Name

pip install langchain langchain_core langserve langgraph fastapi langchain_openai sse_starlette faiss-cpu loguru mypy pandas openpyxl overrides Jinja2 jsonschema black pandas-stubs

# Name 是环境的名，任取。
# 如果用vscode 进行代码调试，需要用 >Python Interpreter. 将python环境指向这个Name代表的环境
```

## 严格模式检查
- mypy --strict run_terminal_rpg_game.py run_rpg_game_server.py run_python_rpg_client.py batch_agent_app_launcher.py game_sample/gen_game.py game_sample/base_form_prompt_editor.py game_sample/actor_profile_prompt_editor.py game_sample/actor_conversational_style_prompt_editor.py game_sample/agentpy_templates/azure_chat_openai_gpt_4o_graph_base_template.py
- mypy --strict run_test_lang_serve.py


## 说明
- game_sample/gen_game.py 是生成游戏世界的配置
- batch_agent_app_launcher.py 可以批量启动agent
- run_terminal_rpg_game.py 利用终端启动游戏，方便调试
- run_rpg_game_server.py 启动一个服务器
- run_python_rpg_client.py 模拟一个网页客户端，与run_game_server.py进行交互。

## Windows平台运行问题
- agent的server代码报错：UnicodeEncodeError: 'gbk' codec can't encode character '\u26a0' in position 0: illegal multibyte sequence 
    - 在Windows的环境变量中加入 `PYTHONIOENCODING=utf-8`


## 升级langchain
- pip install --upgrade langchain langchain_core langserve langchain_openai langchain-community 
- pip show langchain langchain_core langserve langchain_openai langchain-community

## 自动化测试 (安装)
- conda install pytest