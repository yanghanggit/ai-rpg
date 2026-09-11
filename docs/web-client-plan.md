# Web 客户端计划与建议

> 定位：为 AI-RPG 开发面向玩家的 Web 客户端。本文是项目规划与技术选型建议，属工程计划文档，不属于 `wiki/` 下的游戏系统设计文档。

## 目标与定位

- 后端 `scripts/run_game_server.py` 已是一个完整的 FastAPI 服务，Web 客户端因此是一个**纯前端项目**，只消费 HTTP 接口，与后端完全解耦。
- `src/ai_rpg/tui/` 是面向后端开发者的测试工具（手动走查 API 流程与游戏状态），Web 客户端是正式玩家入口，两者是平行消费者、互不替代，共同验证同一套接口。

## 核心判断：后端已 Web 就绪

后端已经具备 Web 前端所需的能力，无需为 Web 客户端改动后端：

| 能力 | 现状 |
| ------ | ------ |
| REST 路由 | login / new_game / home / dungeon / combat / stages / tasks 等已按领域拆分 |
| 实时推送 | 会话新消息与后台任务完成均以 SSE 提供（GET + `text/event-stream`），浏览器原生 EventSource 可直接接入 |
| 跨域 | CORS 已放开（`allow_origins=["*"]`） |
| 图片 | 生成图片经 StaticFiles 挂载为静态 URL，前端直接渲染 |
| 契约 | FastAPI 自动产出 OpenAPI（`/openapi.json`），根路由 `/` 列出全部路由 |
| 数据模型 | 请求/响应统一收敛于 `src/ai_rpg/models/api.py` 的 Pydantic 模型，是类型生成的单一事实源 |

## 仓库结构：独立仓库，不做 mono-repo

- 新建 `ai-rpg-web` 仓库，与 `ai-rpg` 平级独立，互不包含。
- 理由：前后端在构建、依赖、部署、CI 上完全独立；二者唯一需要共享的是 API 契约，而契约同步靠类型生成解决，不靠同一仓库。
- 应避免：在后端仓库根放置 `package.json`、用 FastAPI 的 StaticFiles 托管前端构建产物、把 `web/` 目录塞进 `src/`。

## 技术选型

游戏客户端是典型 SPA，无需 SSR/SEO，选择"无聊但可靠"的组合：

| 项 | 建议 | 理由 |
| ------ | ------ | ------ |
| 构建 | Vite + React + TypeScript（或 SvelteKit） | 生态成熟、开发体验好 |
| 服务端状态 | TanStack Query | 天然适配"命令 → 轮询/SSE → 状态刷新"模式 |
| 客户端状态 | Zustand（可选） | 仅存纯 UI 状态（选中卡牌、弹窗），游戏数据一律交给 Query |
| 实时推送 | 原生 EventSource | 后端 SSE 已是 GET 形式，开箱即用 |
| 后端地址 | 环境变量 `VITE_API_BASE_URL` | 区分本地/联调/生产 |

不建议一开始引入 Next.js、复杂状态机或 WebSocket——先顺着后端既有的 REST + SSE 走。

## API 契约同步：OpenAPI 生成类型

这是避免前后端漂移的关键：

- 后端自动产出 `/openapi.json`，前端用 `openapi-typescript`（或 `@hey-api/openapi-ts`）在构建期生成类型定义。
- 前端所有请求/响应类型均来自生成物，不手写，避免重复维护 `server_client.py` 那样的一长串模型名。
- 后端改模型后，前端重新生成即可同步。

## 通信架构

| 场景 | 方式 |
| ------ | ------ |
| 命令/动作（登录、出牌、合成、进副本） | REST POST |
| 状态查询（场景/副本/战斗状态） | REST GET + TanStack Query |
| 会话新消息 | SSE（EventSource） |
| 后台任务完成 | SSE（`/api/tasks/v1/watch/{job_id}`） |

将来出现实时双向需求（聊天、多人同步）时再引入 WebSocket，当前不需要。

## 认证

- 当前为开发态：`/api/login/v1/` 仅凭 `user_name` 登录并建房，不校验密码、不签发 token。
- JWT 基础设施已就绪（`auth/jwt.py` 与 `services/auth_dependencies.py` 的 OAuth2 依赖），只是尚未接入游戏路由。
- 前端策略：先用用户名直连做原型；上线前再接通 JWT（login 返回 token → 前端存储 → 请求携带 Bearer 头），该步骤属后端改动，接口形态已预留。

## 落地里程碑

对齐 TUI 的命令流（登录 → 家园 → 副本 → 战斗）逐段推进：

1. 脚手架：独立仓库 + Vite 模板，接 `/` 展示服务信息，配好 base URL 与 CORS。
2. 登录与开局：`login` → `new_game` → `stages_state`，搭出页面框架。
3. 家园：home 系列接口，接后台任务 SSE（如生成副本）。
4. 副本：dungeon opening / lifecycle 流程。
5. 战斗：combat 出牌、回合、结算，接会话消息 SSE。
6. 图片展示：直接渲染后端静态图片 URL。

## 与 TUI 客户端的关系

- `src/ai_rpg/tui/` 继续作为后端开发者的走查工具，不面向玩家。
- Web 客户端是正式玩家客户端，两者消费同一套 REST/SSE 接口，互为接口一致性校验。

## 注意事项

- CORS 现为 `*`，仅限开发期；生产需收紧到具体域名。
- SSE 需处理断线重连与事件序号去重。
- 图片渲染依赖后端静态路由前缀，前端应避免硬编码路径。
