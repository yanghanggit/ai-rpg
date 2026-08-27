# 战斗管道（Combat Pipeline）

---

## 定位

战斗管道是副本模式下驱动整个战斗生命周期的 ECS 处理器链。管道以单次 `process()` 为心跳——系统按注册顺序线性执行，顺序即因果链，无事件总线、无中心化状态机。

管道承载四类阶段：**仅首次**（初始化）、**循环**（出牌-仲裁-结算）、**仅末次**（归档清理）、**始终**（入场/收尾）。系统通过自身守卫（检查组件是否存在、战斗状态是否匹配）自行决定是否执行，管道本身不分叉。

→ 参见：[LLM 生成型游戏对象：Card](llm-generated-objects.md)（管道中 LLM 产出的核心对象的完整链路）

---

## 设计决策

### 管道心跳驱动

所有系统共享同一 `process()` 调用周期，按注册顺序执行。抽牌一定在决策之前，结算一定在出牌之后——这种线性编排是因果依赖的唯一保证。没有优先级队列，没有异步回调，调试只需沿注册顺序追踪。

### 场景实体担任仲裁者

出牌结算、消耗品使用、装备使用均由场景实体（stage entity）作为 LLM 仲裁者统一处理，而非由出牌者或目标自行计算。设计意图：场景实体持有完整的战场上下文（每轮仲裁叙事、所有角色的 HP 变化通知），能产出叙事一致的结算结果。出牌仲裁额外读入卡牌的 description，作为叙事种子——结合场景环境、目标状态与即时词缀做「故事泛化」产出 narrative，description 只影响演出措辞，伤害仍按确定性规则结算。仲裁结果通过 `CombatArbitrationEvent` 广播，角色只接收自己视角的叙事片段。

→ 参见：[消耗品系统（ConsumableItem）](consumable-item.md)（相同的仲裁模式，消耗品使用时场景实体统一结算）

### 决策与结算分离

出牌分两步：先决策（选牌选目标），再仲裁（算伤害算效果）。`MonsterPrePlaySystem` / `PartyPrePlaySystem` 用角色自身的 LLM 上下文做决策，产出确定性的 `PlayCardsAction`。`PlayCardsArbitrationSystem` 用场景实体做仲裁，产出叙事文本和数值变化。分离后决策可并行（多个怪物同时思考），仲裁保持单线程（叙事一致），且决策 LLM 不受仲裁风格干扰。

### 回合行动序列

回合按 `creation_order`（角色创建顺序）排列行动顺序，确定性且可复现。回合完成的标志是所有存活角色均已 pass turn，与 energy 是否耗尽无关（耗尽仅限制能打出的牌数，不自动 pass）。

---

## 阶段划分

### 初始化

`CombatInitActorSystem` 为参战角色挂载空牌堆、注入战场上下文。`CombatInitStageSystem` 切换战斗状态为 `ONGOING`、判定场景环境效果。牌库生成由 `GenerateDeckActionSystem` 并行完成，关键词来自角色预置的 `ArchetypeComponent.keywords`。

### 回合循环

抽牌 → DRAW 效果调整 → AI 做出牌决策 → 动作执行 → 场景实体仲裁结算 → 场景塞牌评估。循环的每一轮即一次 `process()` 心跳。

### 回合末

回合完成判定 → 清理旧手牌 → 死亡处理 → 胜负判定 → 新回合创建（按 creation_order 排序）。胜负判定为终局分支点：一旦分出胜负，直接跳至战斗后处理。

### 战斗后

`CombatLootSystem` 按怪物推理掉落。`CombatArchiveSystem` 生成总结、压缩历史、触发记忆存储（内部守卫确保仅执行一次）。`CombatPileTeardownSystem` 将三堆卡牌归还原牌组。

---

## 跨系统关系

- **副本生成管道**产出 `CombatRoom`（stage + actors + keywords），战斗管道消费它 → 参见：[副本生成管道](dungeon-generation.md)
- **装备系统**提供出牌时的 `on_play_affixes`，与卡牌的即时词缀共同参与 `PlayCardsArbitrationSystem` 的本次结算 → 参见：[装备系统](gear-item.md)
- **消耗品系统**走同一场景实体仲裁模式 → 参见：[消耗品系统](consumable-item.md)
- 战斗结束后 `CombatArchiveSystem` 触发记忆存储，衔接家园模式的叙事连续性
