# 地牢生成管线（Dungeon Generate Pipeline）

> 工厂函数：`create_dungeon_generate_pipeline`  
> 源码：`src/ai_rpg/game/tcg_game_process_pipeline.py`  
> 上级入口：[[overview]]

---

## 适用场景

此管线为**离线/按需**管线，与家园管线和战斗管线的运行时性质不同。  
它不处理任何游戏交互，只负责调用 LLM **生成新地牢的全套内容**并输出到文件。

> 重要区分：此管线生成的是地牢的**数据定义**（JSON + 图片文件），不创建运行时 Entity。  
> 将生成数据实例化为游戏内实体是 `setup_dungeon` 的职责，与本管线无关。

---

## 执行顺序

| 步骤 | System | 类型 | 职责 |
| ------ | -------- | ------ | ------ |
| 1 | `PrologueSystem` | Execute | 管线入口 → [[systems-shared#PrologueSystem]] |
| 2 | `GenerateDungeonActionSystem` | Reactive | Steps 1-4：LLM 生成地牢文本数据 |
| 3 | `IllustrateDungeonActionSystem` | Reactive | Step 5：生成地牢配图 |
| 4 | `ActionCleanupSystem` | Execute | 清理 Action → [[systems-shared#ActionCleanupSystem]] |
| 5 | `DestroyEntitySystem` | Execute | 销毁标记实体 → [[systems-shared#DestroyEntitySystem]] |
| 6 | `EpilogueSystem` | Execute | flush 状态 → [[systems-shared#EpilogueSystem]] |

---

## 核心系统详解

### GenerateDungeonActionSystem — Steps 1-4（步骤 2）

**源码**：`src/ai_rpg/systems/generate_dungeon_action_system.py`  
**监听**：`GenerateDungeonAction`

分四步串行调用 LLM，输出结果写入 `DUNGEONS_DIR` 下的 JSON 文件：

| Step | 生成内容 | 输出字段 |
| ------ | ---------- | ---------- |
| Step 1 | 地牢生态环境 | `name` / `ecology` |
| Step 2 | 房间列表与布局 | `rooms[]`（含房间名、描述、类型） |
| Step 3 | 敌人配置 | 每个房间的 `enemies[]`（角色表 `CharacterSheet`） |
| Step 4 | 物品与道具 | 每个房间的 `items[]` |

世界观框架（战役设定 `RPG_CAMPAIGN_SETTING` + 规则系统 `RPG_SYSTEM_RULES`）通过 `SystemMessage` 注入，所有 LLM 调用都在此世界观约束下生成内容。

---

### IllustrateDungeonActionSystem — Step 5（步骤 3）

**源码**：`src/ai_rpg/systems/illustrate_dungeon_action_system.py`  
**监听**：`IllustrateDungeonAction`

读取 Step 1-4 生成的地牢文本数据，为每个场景（房间）调用图片生成服务，输出图片文件到 `generated_images/` 目录。

---

## 与运行时管线的对比

| 维度 | 地牢生成管线 | 家园 / 战斗管线 |
| ------ | ------------- | ---------------- |
| 触发频率 | 按需一次性 | 每帧循环 |
| 操作对象 | 文件系统（JSON + 图片） | 运行时 Entity / Component |
| LLM 调用目的 | 创作内容 | 驱动游戏逻辑 |
| 与玩家交互 | 无 | 有 |
