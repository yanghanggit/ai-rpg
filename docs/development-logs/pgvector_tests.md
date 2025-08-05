# pgvector 综合测试

这个测试文件提供了 pgvector 功能的完整测试套件，包括基础 SQL 操作、ORM 操作和实际应用场景演示。

## 环境配置

首先激活 conda 环境：

```bash
conda activate first_seed
```

## 运行测试

### 运行所有数据库测试

```bash
cd /Users/yanghang/Documents/GitHub/multi-agents-game-framework
python -m pytest tests/integration/test_pgvector_comprehensive.py -m "database" -v
```

### 运行单个测试

```bash
# 基础向量操作测试
python -m pytest tests/integration/test_pgvector_comprehensive.py::test_basic_vector_operations -v -s

# 高维向量测试
python -m pytest tests/integration/test_pgvector_comprehensive.py::test_high_dimension_vectors -v -s

# 文档向量操作测试
python -m pytest tests/integration/test_pgvector_comprehensive.py::test_vector_document_operations -v -s

# 对话向量操作测试
python -m pytest tests/integration/test_pgvector_comprehensive.py::test_conversation_vector_operations -v -s

# 游戏知识向量操作测试
python -m pytest tests/integration/test_pgvector_comprehensive.py::test_game_knowledge_operations -v -s
```

### 运行演示测试

```bash
# 运行所有演示（较慢）
python -m pytest tests/integration/test_pgvector_comprehensive.py -m "demo" -v -s

# 运行综合演示
python -m pytest tests/integration/test_pgvector_comprehensive.py::test_comprehensive_pgvector_demos -v -s
```

### 运行完整的综合测试

```bash
python -m pytest tests/integration/test_pgvector_comprehensive.py::test_comprehensive_pgvector_integration -v -s
```

## 直接运行脚本

您也可以直接运行测试脚本，它提供了命令行参数选项：

```bash
cd tests/integration

# 运行所有测试
python test_pgvector_comprehensive.py

# 只运行基础 SQL 测试
python test_pgvector_comprehensive.py --mode basic

# 只运行 ORM 测试
python test_pgvector_comprehensive.py --mode orm

# 只运行演示
python test_pgvector_comprehensive.py --mode demo
```

## 测试标记

测试使用了以下 pytest 标记：

- `@pytest.mark.integration`: 集成测试
- `@pytest.mark.database`: 数据库相关测试
- `@pytest.mark.demo`: 演示测试
- `@pytest.mark.slow`: 慢速测试
- `@pytest.mark.comprehensive`: 综合测试

## 测试内容

### 基础 SQL 向量操作测试

- pgvector 扩展检查
- 基本向量操作（3维向量）
- 高维向量操作（1536维向量）
- 向量相似度搜索
- 余弦相似度计算

### ORM 向量操作测试

- 向量文档保存和搜索
- 对话向量保存和搜索
- 游戏知识向量保存和搜索
- 数据库统计信息获取

### 实际应用场景演示

- 基于文档的 RAG 系统演示
- 对话记忆系统演示
- 游戏知识系统演示

## 注意事项

1. 确保 PostgreSQL 数据库正在运行
2. 确保已安装 pgvector 扩展
3. 确保环境变量和数据库配置正确
4. 测试会在数据库中创建和删除临时表，请确保有相应权限

## 故障排除

如果遇到导入错误，请确保：

1. 已激活正确的 conda 环境 (`conda activate first_seed`)
2. 在项目根目录运行测试
3. 所有依赖包已正确安装
