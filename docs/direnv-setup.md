# 使用 direnv 自动激活虚拟环境

## 配置说明

本项目已配置 `direnv` 来自动激活 uv 虚拟环境。

### 一次性设置（已完成）

1. ✅ 已安装 direnv: `brew install direnv`
2. ✅ 已在 `~/.zshrc` 添加 hook: `eval "$(direnv hook zsh)"`
3. ✅ 已创建 `.envrc` 文件
4. ✅ 已授权: `direnv allow .`

### 使用方法

**自动激活：**
打开新终端，`cd` 到项目目录，direnv 会自动激活虚拟环境：

```bash
cd ~/Documents/GitHub/ai-rpg
# direnv: loading ~/Documents/GitHub/ai-rpg/.envrc
python --version  # 自动使用 .venv 中的 Python
```

**离开目录自动卸载：**

```bash
cd ~  # 环境会自动卸载
```

### 验证配置

检查 Python 路径：

```bash
which python
# 应该显示: /Users/yanghang/Documents/GitHub/ai-rpg/.venv/bin/python
```

### 常见问题

**Q: 提示 `direnv: error .envrc is blocked`**
A: 运行 `direnv allow .` 授权

**Q: 修改 `.envrc` 后不生效**
A: 再次运行 `direnv allow .`

**Q: 新终端不生效**
A: 确保 `~/.zshrc` 包含: `eval "$(direnv hook zsh)"`
