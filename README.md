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
mypy --strict run_terminal_tcg_game.py run_tcg_game_server.py run_chat_server.py
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

## Windows平台运行问题

- agent的server代码报错：UnicodeEncodeError: 'gbk' codec can't encode character '\u26a0' in position 0: illegal multibyte sequence 
  - 在Windows的环境变量中加入 `PYTHONIOENCODING=utf-8`

# Winsows平台使用WSL配置环境
## 安装WSL和Linux系统
可以follow[这篇文档](https://learn.microsoft.com/zh-cn/windows/wsl/install)
```shell
# 1.管理员身份运行CMD

# 2.安装wsl，运行：
wsl --install

# 3.安装系统，运行：
wsl --install -d Ubuntu-24.04

# 4.安装过程中配置用户名和密码
```
## 配置环境
### 安装Miniconda或Anaconda
```shell
# 下载安装包
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh

# 运行安装包(与安装包同路径下)
bash Miniconda3-latest-Linux-x86_64.sh
```
随后配置python环境的步骤同[前文](#依赖包安装)。
### 安装PM2
```shell
# 首先确保安装了Node.js和npm
node -v
npm -v

# 若未安装，运行以下命令安装
sudo apt update
sudo apt install nodejs npm

# 安装PM2
npm install -g pm2

# 检测安装是否成功
pm2 --version
```
### 安装git
```shell
sudo apt install git
git --version
```
### 安装zsh(optional)
```shell
# 用于配置每次开shell前导入的环境变量等，嫌麻烦可以直接写进.bashrc
# 安装
sudo apt-get install zsh

# 运行zsh，运行后按0退出，随后在.zshrc中配置key即可
zsh

# 程序首次运行前，需要在运行程序的shell中(即VScode的终端中)运行一次
source ~/.zshrc
```
### 配置代理(optional)

以v2rayN为例

如果要在wsl中使用代理需要从windows宿主机的局域网端口连接
1. 在代理软件中允许来自局域网的连接
2. windows防火墙中给代理软件白名单
3. 添加代理，写进.zshrc或.bashrc都行
```shell
# 添加http/https代理, apt代理, git代理
export hostip=$(ip route | grep default | awk '{print $3}')
export hostport=10809
alias proxy='
    export https_proxy="http://${hostip}:${hostport}";
    export http_proxy="http://${hostip}:${hostport}";
    export all_proxy="http://${hostip}:${hostport}";
    git config --global http.proxy "http://${hostip}:${hostport}"
    git config --global https.proxy "http://${hostip}:${hostport}"
    echo -e "Acquire::http::Proxy \"http://${hostip}:${hostport}\";" | sudo tee -a /etc/apt/apt.conf.d/proxy.conf > /dev/null;
    echo -e "Acquire::https::Proxy \"http://${hostip}:${hostport}\";" | sudo tee -a /etc/apt/apt.conf.d/proxy.conf > /dev/null;
'
alias unproxy='
    unset https_proxy;
    unset http_proxy;
    unset all_proxy;
    git config --global --unset http.proxy
    git config --global --unset https.proxy
    sudo sed -i -e '/Acquire::http::Proxy/d' /etc/apt/apt.conf.d/proxy.conf;
    sudo sed -i -e '/Acquire::https::Proxy/d' /etc/apt/apt.conf.d/proxy.conf;
'
```
4. 运行
```bash
proxy
```
## 配置VScode
具体可以参考[官方文档](https://code.visualstudio.com/docs/remote/wsl)
1. 安装WSL插件
2. 把项目clone到虚拟环境中，open folder选择项目文件夹，随后点击弹窗中的```open in wsl```
3. 打开Extensions，在WSL环境中安装需要的插件，如Copilot，Python，Python Debugger，Pylance...
### 配置VScode代理

需要用copilot的情况，vscode不走wsl的代理，需要单独设置。

1. 打开File->Preferences->Settings，搜索proxy
2. 配置如下，ip地址换成自己的，可以直接echo $https_proxy
```
{
    "http.proxySupport": "on",
    "http.proxy": "http://172.28.0.1:10809",
    "http.proxyAuthorization": null,
    "http.proxyStrictSSL": false
}
```