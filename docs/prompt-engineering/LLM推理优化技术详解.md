# LLM推理优化技术详解

## KV缓存 (Key-Value Cache)

### 核心概念

KV缓存是Transformer架构中的重要优化技术，用于加速文本生成过程。

### 工作原理

1. **首次处理**: 输入prompt时，计算并缓存所有token的Key和Value矩阵
2. **增量生成**: 生成新token时，只计算新token的K、V，复用缓存中的历史数据
3. **注意力计算**: 新token的Query与缓存中所有K进行注意力计算

### 主要优势

- **速度提升**: 避免重复计算，显著加快生成速度（特别是长文本）
- **降低计算量**: 时间复杂度从 $O(n^2)$ 降至 $O(n)$

### 内存开销

每个token需要存储：

- Key向量: `[num_layers, hidden_size]`
- Value向量: `[num_layers, hidden_size]`

### 重要区别

- **KV缓存**: 提高推理速度，不节省token费用
- **Prompt Caching**: 降低重复token费用（需API支持）

---

## 破坏KV缓存效率的操作

### 1. 修改历史消息

- 编辑之前的对话内容
- 删除中间的某条消息
- 插入新消息到历史记录中间
- **后果**: 缓存失效，需要重新计算所有token

### 2. 改变System Prompt

- 修改系统提示词
- 调整角色设定
- 更新指令模板
- **后果**: 整个缓存作废，从头开始

### 3. Token序列不连续

- 跳过某些对话轮次
- 重新排序消息
- 使用不同的tokenizer处理相同文本
- **后果**: 无法匹配缓存，必须重算

### 4. 上下文截断策略不当

```python
# ❌ 错误: 从中间截断
messages = messages[-10:]  # 丢失前面的缓存

# ✅ 正确: 保留开头+截断中间
messages = [system_msg] + recent_messages[-9:]
```

### 5. 频繁切换话题/重置对话

- 每次都清空历史
- 短对话后就重新开始
- **后果**: 无法积累缓存优势

### 6. 批处理时的提示词不一致

```python
# ❌ 每个请求都不同的开头
prompts = [
    "Please help: " + query1,
    "Can you: " + query2,
]

# ✅ 共享前缀
prompts = [
    common_prefix + query1,
    common_prefix + query2,
]
```

### 最佳实践

1. **只追加新内容**: 始终在对话末尾添加
2. **固定System Prompt**: 整个会话期间保持不变
3. **智能截断**: 保留关键上下文（开头+最近消息）
4. **批量共享前缀**: 利用prefix caching优化
5. **避免频繁重置**: 尽量延长对话生命周期

---

## 采样参数详解

### top_p (核采样 / Nucleus Sampling)

**范围**: 0.0 - 1.0

**作用**: 从累积概率达到p的最小token集合中采样

```python
# 例如 top_p=0.9
# 假设token概率分布:
# "is": 0.4, "was": 0.3, "are": 0.15, "were": 0.1, "be": 0.05
# 
# 累积到0.9: "is"(0.4) + "was"(0.3) + "are"(0.15) + "were"(0.1) = 0.95
# 只从前4个token中采样，忽略"be"
```

**效果**:

- `top_p=1.0`: 考虑所有token（最随机）
- `top_p=0.9`: 常用值，平衡创造性和连贯性
- `top_p=0.1`: 非常保守，输出确定性高

### top_k (Top-K采样)

**范围**: 整数，如 1, 10, 40, 50

**作用**: 只从概率最高的k个token中采样

```python
# 例如 top_k=3
# 只考虑概率最高的3个token:
# "is": 0.4, "was": 0.3, "are": 0.15
# 其他全部忽略
```

**效果**:

- `top_k=1`: 贪婪解码，总是选最高概率（确定性输出）
- `top_k=40-50`: 常用值
- `top_k=无限大`: 等同于不限制

### repetition_penalty (重复惩罚)

**范围**: 通常 1.0 - 2.0

**作用**: 降低已出现过的token再次被选中的概率

```python
# 例如 repetition_penalty=1.2
# 已生成: "the cat sat on the"
# 
# 原始概率: "mat"=0.3, "the"=0.25, "floor"=0.2
# 应用惩罚后: "mat"=0.3, "the"=0.25/1.2=0.208, "floor"=0.2
# "the"因为出现过而被惩罚
```

**效果**:

- `1.0`: 无惩罚
- `1.1-1.3`: 温和减少重复（常用）
- `1.5+`: 强力避免重复，可能导致语义不连贯

---

## 实用配置方案

### 创意写作

```python
{
    "temperature": 0.8,
    "top_p": 0.95,
    "top_k": 50,
    "repetition_penalty": 1.1
}
```

### 代码生成

```python
{
    "temperature": 0.2,
    "top_p": 0.9,
    "top_k": 40,
    "repetition_penalty": 1.0
}
```

### 精确任务（翻译/摘要）

```python
{
    "temperature": 0.3,
    "top_p": 0.9,
    "top_k": 10,
    "repetition_penalty": 1.05
}
```

---

## 关键要点总结

| 技术 | 主要作用 | 是否节省费用 |
|------|----------|--------------|
| **KV缓存** | 加快推理速度 | ❌ 否 |
| **Prompt Caching** | 降低重复token费用 | ✅ 是（需API支持） |

### 采样参数使用建议

- `top_p`和`top_k`通常**只选一个**使用
- `repetition_penalty`可以与其他参数组合
- 过高的`repetition_penalty`会让模型"刻意避免"合理的重复词
- 采样参数改变不影响KV缓存本身，但可能导致生成路径完全不同

---

创建日期: 2025年11月22日
