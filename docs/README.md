# AI-RPG 知识库根节点

> 这是 `docs/` 目录的唯一入口。每次新增文档领域时，请在此处更新索引。
> Agent 从此处出发，可定位到任何知识。

---

## 项目简介

**ai-rpg** 是一款融合 TCG 卡牌战斗机制的 AI 驱动 RPG 游戏。  
核心技术栈：Python · ECS（自研 entitas） · LangChain · ChromaDB · FastAPI

关键概念：`Entity` / `Component` / `System` / `Pipeline` / `ReactiveProcessor` / `LLM Agent`

---

## 知识领域索引

| 领域 | 内容摘要 | 入口文档 |
| ------ | ---------- | ---------- |
| **ECS 管线设计** | 三条游戏流程管线（家园/战斗/地牢生成）的架构、系统执行顺序与设计模式 | [ecs-pipeline/overview.md](ecs-pipeline/overview.md) |

---

## 更新日志

| 日期 | 变更 |
| ------ | ------ |
| 2026-04-13 | 初始化知识库；新增 `ecs-pipeline/` 系列文档（7 篇） |
