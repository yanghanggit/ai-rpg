# 公共知识检索系统（RAG / QueryAction）

---

## 定位

RAG 系统为 AI 角色提供「向世界提问」的能力。任何角色可发起 `QueryAction`，以自然语言从 pgvector 向量数据库中检索该游戏世界的公共知识。检索结果作为 `HumanMessage` 注入角色记忆，供后续决策参考。

核心设计决策是**公共记忆与私人记忆的二元分离**：`Blueprint.knowledge_base` 承载任何路人都可观察到的客观环境事实，经向量化存入 pgvector；角色的身世、性格、秘密等私人知识由各自 `profile` 字段承载，不进入向量库。二者互不污染——角色不知道的事，不能通过 RAG「顺便知道」。

---

## 知识库内容的编排约束

`knowledge_base` 是 `Dict[str, List[str]]`，key 为分类名，value 为该分类下的文档条目。内容编排遵循严格约束：仅写入感官层面的客观环境事实（建筑外观、气味、声音）；禁止人物信息、解释性判断、阵营立场、叙事秘密。单蓝图条目数控制在 5 条以内，控制 RAG 检索噪声。

这些约束服务于同一目标：公共知识库必须中立、紧凑，既不泄露叙事秘密，也不污染角色的独立认知。如果一条信息需要「特定身份」或「特定认知阶段」才能知晓，它就不该出现在这里。

---

## 两阶段生命周期

**初始化阶段**由 `_setup_rag` 执行：读取 `BLUEPRINTS_DIR` 下所有蓝图文件，将每个蓝图的 `knowledge_base` 展开为 `(document, metadata)` 二元组——metadata 记录 `category`。使用 `multilingual_model`（全局共享的 SentenceTransformer 实例）向量化后存入 `vector_documents` 表，余弦相似度度量。每个游戏拥有独立 `collection`（以游戏名命名的列值），实现多世界向量空间隔离。`vector_documents` 表随 PostgreSQL 数据库在开发环境初始化阶段一并重建，保证每次重建为干净状态。

**运行时阶段**由 `QueryActionSystem` 驱动：作为 ECS `ReactiveProcessor`，监听 `QueryAction` 组件的 `ADDED` 事件。对每个携带 `QueryAction` 的实体，将其 `question` 向量化后在当前游戏 `collection` 中执行语义搜索，返回 `top_k`（默认 3）条结果。pgvector 原生的余弦距离在 `search_documents` 中被转换为 [0, 1] 区间的相似度分数（`1 - cosine_distance`）。

---

## QueryActionSystem 的触发与消费

`QueryActionSystem` 是被动响应式系统：不主动驱动游戏进程，仅当其他系统或 AI 角色生成 `QueryAction` 并挂载到实体时触发。检索完成后产出一条 `HumanMessage`，进入实体的消息历史，被后续 LLM 调用的消息历史构建过程消费。系统本身不解释检索结果——解释权完全交给接收消息的 AI 角色。

`QueryAction` 由 `HomeNpcPlanSystem` 根据 LLM 的行动决策生成。`query` 可与 `speak` / `whisper` / `announce` / `trans_stage` 同轮并用，互不阻塞。

## 提示词分层

`query` 的引导分布在两层：

- **宪法层**（`RPG_SYSTEM_RULES`）：不提及 `query`。仅声明原则——世界的公共事实不由角色编造，需从外部知识库获取；角色的推断与意见是扮演的合法部分。
- **任务层**（`build_action_planning_prompt`）：告知 `query` 可从外部知识库获取信息，可与任何行动同轮并用。

分层的意图：系统提示词是角色的「世界观宪法」，不应出现具体行动机制；行动机制留给每轮的任务提示词，按需告知。

---

## 相似度分数作为元信息

检索结果消息中内嵌相似度阈值指南（>0.70 高度相关 / 0.55–0.70 中等 / <0.55 低相关），引导 AI 自行判断是否采信，系统不做硬性过滤。同时消息中提示「避免对同一问题重复查询」，防止 AI 陷入无效的重复检索循环。空结果同样产出一条明确声明「目前没有相关信息」的消息，让 AI 知晓检索已完成而非卡住。

---

## 跨系统关联

- `Blueprint.knowledge_base` 是数据定义端，`_setup_rag` 是数据加载端，`QueryActionSystem` 是数据消费端。三者构成「定义 → 向量化 → 检索」完整链路。
- pgvector 知识检索模块（`rag/knowledge_retrieval.py`）提供纯工具层：`add_documents` 执行批量向量化与写入 `vector_documents` 表，`search_documents` 按 `collection` 过滤执行语义搜索与相似度转换。该模块桥接 `SentenceTransformer` 嵌入模型与 pgvector 存储层（`pgsql` 包），不感知游戏业务逻辑；`pgsql` 层本身不引用 `SentenceTransformer`，仅提供纯粹的向量存取操作。
- `multilingual_model` 是全局共享的 SentenceTransformer 实例，初始化脚本和运行时检索共用同一模型，保证向量空间一致。
- 检索产出的 `HumanMessage` 与角色 profile、场景描述等一同进入 LLM 消息历史构建管道，影响角色的后续行动决策。
- 与工坊合成、副本生成共享同一架构原则（机制与内容分离）：`knowledge_base` 的内容完全由蓝图配置决定，检索系统代码不包含任何世界观相关硬编码。

→ 参见：[工坊合成管道（Craft Pipeline）](craft-pipeline.md)
→ 参见：[副本生成管道（Dungeon Generation Pipeline）](dungeon-generation.md)
