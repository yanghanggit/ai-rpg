# 环境配置说明

本项目支持两种环境配置方式：**推荐使用Conda**用于更好的性能和依赖管理。

## 🚀 推荐：Conda环境安装

### 安装步骤

```bash
# 克隆仓库
git clone <repository-url>
cd multi-agents-game-framework

# 创建并激活conda环境
conda env create -f environment.yml
conda activate first_seed

# 安装本地项目包（开发模式）
pip install -e .
```

### Conda环境优势

- ✅ **性能优化**：numpy、pandas等科学计算包使用conda版本，性能更好
- ✅ **依赖管理**：系统级依赖（如编译器、数据库驱动）由conda管理
- ✅ **版本一致**：所有包版本经过兼容性测试
- ✅ **跨平台**：macOS ARM64、x86_64、Linux完全兼容

### 包分布策略

- **Conda包（84个）**：系统级依赖、编译型包、科学计算包
- **Pip包（81个）**：Python特定包、AI/ML框架、应用级依赖

## 🔧 备用：传统Pip安装

如果无法使用conda，可以使用传统pip安装：

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 安装开发依赖（可选）
pip install -r requirements-dev.txt

# 安装本地项目包
pip install -e .
```

### ⚠️ 注意事项

使用pip安装时可能需要手动安装系统依赖：

```bash
# macOS
brew install postgresql libpq

# Ubuntu/Debian
sudo apt-get install postgresql-dev libpq-dev

# CentOS/RHEL
sudo yum install postgresql-devel
```

## 📦 环境验证

安装完成后，运行以下命令验证环境：

```bash
# 类型检查
mypy --strict scripts/ src/ tests/

# 运行测试
pytest tests/ -v

# 检查依赖冲突
pip check
```

## 🔄 环境更新

### 更新Conda环境

```bash
conda env update -f environment.yml --prune
```

### 更新Pip环境

```bash
pip install -r requirements.txt --upgrade
```

## 📋 开发工具

环境包含以下开发工具：

- **类型检查**：mypy 1.16.0
- **代码格式化**：black 25.1.0、ruff 0.12.5
- **测试框架**：pytest 8.3.4
- **Git钩子**：pre-commit 4.2.0

## 🆘 故障排除

### 常见问题

1. **M1/M2 Mac用户**：使用conda能自动处理ARM64架构
2. **依赖冲突**：运行 `pip check` 检查并解决
3. **包缺失**：确保使用正确的requirements文件
4. **权限问题**：避免使用 `sudo pip install`

### 环境重建

```bash
# 删除旧环境
conda env remove -n first_seed

# 重新创建
conda env create -f environment.yml
```
