#!/usr/bin/env python3
"""
游戏 MCP 服务器 - 基于配置文件的生产级实现

基于 MCP 2025-06-18 规范的 Streamable HTTP 传输实现。

架构特点：
1. 标准 Streamable HTTP 传输（MCP 2025-06-18 规范）
2. 支持 Server-Sent Events (SSE) 流
3. 会话管理和安全控制
4. 生产级特性：日志记录、错误处理、资源管理
5. 专注于 RAG 知识库查询功能
6. 完全基于配置文件的设计，消除硬编码

设计原则：
- 配置文件驱动：所有服务器参数都从配置文件读取
- 命令行简化：只需指定配置文件路径和日志级别
- 无默认值：必须显式提供配置文件，出错立即停止
- 极致简化：避免参数冗余和配置歧义

使用方法：

    # 使用指定配置文件启动（必需参数）
    python scripts/run_mcp_server.py --config mcp_config.json

    # 指定日志级别
    python scripts/run_mcp_server.py --config mcp_config.json --log-level DEBUG

    # 使用不同环境的配置文件
    python scripts/run_mcp_server.py --config config/production.json
    python scripts/run_mcp_server.py --config config/development.json

配置文件示例 (mcp_config.json)：
{
  "mcp_server_host": "127.0.0.1",
  "mcp_server_port": 8765,
  "protocol_version": "2025-06-18",
  "mcp_timeout": 30,
  "server_name": "Production MCP Server",
  "server_version": "1.0.0",
  "server_description": "生产级 MCP 服务器，支持工具调用、资源访问和提示模板",
  "transport": "streamable-http",
  "allowed_origins": ["http://localhost"]
}
"""

import os
import sys
import json
from datetime import datetime
from typing import Any, Dict

# 将 src 目录添加到模块搜索路径
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

import click
from loguru import logger
from mcp.server.fastmcp import FastMCP
from multi_agents_game.mcp import McpConfig, load_mcp_config
from multi_agents_game.rag.rag_system import rag_semantic_search
from pathlib import Path

# ============================================================================
# 服务器配置
# ============================================================================


def _get_server_config_dict(mcp_config: McpConfig) -> Dict[str, Any]:
    """获取服务器配置字典"""
    return {
        "name": mcp_config.server_name,
        "version": mcp_config.server_version,
        "description": mcp_config.server_description,
        "transport": mcp_config.transport,
        "protocol_version": mcp_config.protocol_version,
        "started_at": datetime.now().isoformat(),
    }


def _initialize_fast_mcp_server(mcp_config: McpConfig) -> FastMCP:
    """创建 FastMCP 服务器实例"""
    app = FastMCP(
        name=mcp_config.server_name,
        instructions=mcp_config.server_description,
        debug=True,  # HTTP 模式可以启用调试
    )

    # 添加健康检查端点
    _register_health_endpoint(app)
    # 注册工具
    _register_tools(app, mcp_config)

    return app


# ============================================================================
# 健康检查端点
# ============================================================================


def _register_health_endpoint(app: FastMCP) -> None:
    """注册健康检查端点"""
    from fastapi import Request, Response
    import json

    @app.custom_route("/health", methods=["POST"])  # type: ignore[misc]
    async def health_check(request: Request) -> Response:
        """处理 MCP 健康检查请求"""
        try:
            # 解析请求体
            body = await request.body()
            data = json.loads(body.decode("utf-8"))

            # 检查是否是 ping 方法
            if data.get("method") == "ping":
                response_data = {
                    "jsonrpc": "2.0",
                    "id": data.get("id"),
                    "result": {"status": "ok"},
                }
                return Response(
                    content=json.dumps(response_data),
                    media_type="application/json",
                    status_code=200,
                )
            else:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": data.get("id"),
                    "error": {"code": -32601, "message": "Method not found"},
                }
                return Response(
                    content=json.dumps(error_response),
                    media_type="application/json",
                    status_code=200,
                )
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {str(e)}"},
            }
            return Response(
                content=json.dumps(error_response),
                media_type="application/json",
                status_code=400,
            )


# ============================================================================
# 工具实现
# ============================================================================


def _register_tools(app: FastMCP, mcp_config: McpConfig) -> None:
    """注册所有工具"""

    @app.tool()
    async def rag_query(query: str, context_limit: int = 5) -> str:
        """
        艾尔法尼亚RPG世界知识库查询工具

        专门用于查询艾尔法尼亚RPG游戏世界的相关信息，包括：
        - 王国历史和背景设定（阿斯特拉王国、月桂森林联邦、铁爪部族联盟）
        - 角色人物和种族信息（人类、精灵、兽人、勇者、魔王等）
        - 武器装备和道具属性（圣剑晨曦之刃、魔法药水、时之沙漏等）
        - 地图场景和遗迹描述（封印之塔、贤者之塔、暗影墓地等）
        - 魔法技能和战斗系统（五大魔法学派、圣剑技能等）
        - 剧情故事和组织关系（魔王封印、冒险者公会等）

        注意：此工具仅适用于艾尔法尼亚RPG游戏世界相关查询，不处理其他主题。

        Args:
            query: 关于艾尔法尼亚RPG游戏世界的查询问题或关键词
            context_limit: 返回相关上下文的数量限制

        Returns:
            查询结果的JSON字符串，包含相关文档和相似度分数
        """
        try:
            logger.info(
                f"🔍 RAG查询请求: query='{query}', context_limit={context_limit}"
            )

            # 调用RAG语义搜索函数
            documents, similarity_scores = rag_semantic_search(
                query, top_k=context_limit
            )

            # 构建返回结果
            if documents and similarity_scores:
                # 成功检索到相关文档
                results = []
                for i, (doc, score) in enumerate(zip(documents, similarity_scores)):
                    results.append(
                        {
                            "rank": i + 1,
                            "content": doc,
                            "similarity_score": round(score, 4),
                            "relevance": (
                                "high"
                                if score > 0.7
                                else "medium" if score > 0.4 else "low"
                            ),
                        }
                    )

                response = {
                    "status": "success",
                    "query": query,
                    "total_results": len(results),
                    "context_limit": context_limit,
                    "results": results,
                    "timestamp": datetime.now().isoformat(),
                }

                logger.info(f"✅ RAG查询成功，返回 {len(results)} 个相关文档")

            else:
                # 未找到相关文档
                response = {
                    "status": "no_results",
                    "query": query,
                    "total_results": 0,
                    "context_limit": context_limit,
                    "results": [],
                    "message": "未找到与查询相关的文档",
                    "timestamp": datetime.now().isoformat(),
                }

                logger.warning(f"⚠️ RAG查询未找到相关文档: '{query}'")

            return json.dumps(response, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"❌ RAG查询失败: {e}")
            error_result = {
                "status": "error",
                "query": query,
                "context_limit": context_limit,
                "error": str(e),
                "message": f"RAG查询过程中发生错误: {str(e)}",
                "timestamp": datetime.now().isoformat(),
            }
            return json.dumps(error_result, ensure_ascii=False, indent=2)


@click.command()
@click.option(
    "--config",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="MCP配置文件路径（必需）",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    default="INFO",
    help="日志级别",
)
def main(config: Path, log_level: str) -> None:
    """启动游戏 MCP 服务器 (Streamable HTTP)"""

    # 配置日志
    logger.remove()  # 移除默认处理器
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )

    # 加载配置
    try:
        mcp_config = load_mcp_config(config)
    except Exception as e:
        logger.error(f"❌ 配置文件加载失败: {e}")
        raise click.ClickException(f"配置文件加载失败: {e}")

    logger.info(
        f"🎯 启动游戏 MCP 服务器 {mcp_config.server_name} v{mcp_config.server_version}"
    )
    logger.info(f"📡 传输协议: {mcp_config.transport} ({mcp_config.protocol_version})")
    logger.info(
        f"🌐 服务地址: http://{mcp_config.mcp_server_host}:{mcp_config.mcp_server_port}"
    )
    logger.info(f"📝 日志级别: {log_level}")
    logger.info(f"⚙️  配置文件: {config}")
    logger.info(f"🔍 支持功能: RAG知识库查询")

    # 创建应用实例
    app = _initialize_fast_mcp_server(mcp_config)

    # 配置 FastMCP 设置
    app.settings.host = mcp_config.mcp_server_host
    app.settings.port = mcp_config.mcp_server_port

    try:
        # 启动 HTTP 服务器
        logger.info("✅ 游戏 MCP 服务器启动完成，等待客户端连接...")
        app.run(transport="streamable-http")
    except KeyboardInterrupt:
        logger.info("🛑 收到中断信号，正在关闭服务器...")
    except Exception as e:
        logger.error(f"❌ 服务器启动失败: {e}")
        raise
    finally:
        logger.info("👋 游戏 MCP 服务器已关闭")


if __name__ == "__main__":
    main()
