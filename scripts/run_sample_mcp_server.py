#!/usr/bin/env python3
"""
生产级 MCP 服务器

这是一个独立部署的 MCP 服务器进程，设计用于与 MCP 客户端（如 run_deepseek_mcp_chat_client.py）通信。

架构特点：
1. 独立进程运行，可单独部署和管理
2. 支持多种传输协议（stdio、SSE、streamable-http）
3. 标准 MCP 协议实现，兼容所有 MCP 客户端
4. 生产级特性：日志记录、错误处理、资源管理
5. 可扩展的工具和资源系统

使用方法：
    # 启动 stdio 模式（适合与单个客户端通信）
    python scripts/run_sample_mcp_server.py --transport stdio

    # 启动 HTTP 模式（适合多客户端或 Web 集成）
    python scripts/run_sample_mcp_server.py --transport streamable-http --port 8765

    # 启动 SSE 模式（适合 Web 应用）
    python scripts/run_sample_mcp_server.py --transport sse --port 8766
"""

import os
import sys
import json
from datetime import datetime
from typing import Any, Dict, AsyncGenerator

# 将 src 目录添加到模块搜索路径
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

import click
from loguru import logger
from mcp.server.fastmcp import FastMCP
import mcp.types as types


# ============================================================================
# 服务器配置
# ============================================================================


class ServerConfig:
    """服务器配置类"""

    def __init__(self) -> None:
        self.name = "Production MCP Server"
        self.version = "1.0.0"
        self.description = "生产级 MCP 服务器，支持工具调用、资源访问和提示模板"
        self.max_message_size = 10 * 1024 * 1024  # 10MB
        self.timeout = 30  # 30秒超时

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "max_message_size": self.max_message_size,
            "timeout": self.timeout,
            "started_at": datetime.now().isoformat(),
        }


# 全局配置实例
config = ServerConfig()

# 创建 FastMCP 服务器实例
app = FastMCP(
    name=config.name,
    instructions=config.description,
    debug=False,  # 生产环境设置为 False
    log_level="INFO",
)


# ============================================================================
# 工具实现
# ============================================================================


@app.tool()
async def get_current_time(format: str = "datetime") -> str:
    """
    获取当前系统时间

    Args:
        format: 时间格式 (datetime|timestamp|iso|custom)

    Returns:
        格式化的时间字符串
    """
    try:
        now = datetime.now()

        if format == "datetime":
            return now.strftime("%Y-%m-%d %H:%M:%S")
        elif format == "timestamp":
            return str(int(now.timestamp()))
        elif format == "iso":
            return now.isoformat()
        elif format == "custom":
            return now.strftime("%A, %B %d, %Y at %I:%M %p")
        else:
            return now.strftime("%Y-%m-%d %H:%M:%S")

    except Exception as e:
        logger.error(f"获取时间失败: {e}")
        return f"错误：无法获取时间 - {str(e)}"


@app.tool()
async def calculator(expression: str, precision: int = 2) -> str:
    """
    安全的数学计算器

    Args:
        expression: 数学表达式，支持 +, -, *, /, (), 幂运算(**)
        precision: 小数精度（默认2位）

    Returns:
        计算结果或错误信息
    """
    try:
        # 安全字符检查
        allowed_chars = set("0123456789+-*/.() **")
        if not all(c in allowed_chars for c in expression.replace(" ", "")):
            return "错误：表达式包含不允许的字符。仅支持数字和基本运算符 (+, -, *, /, **, ())"

        # 防止过长表达式
        if len(expression) > 200:
            return "错误：表达式过长，请限制在200个字符以内"

        # 安全求值
        result = eval(expression)

        # 处理结果精度
        if isinstance(result, float):
            result = round(result, precision)

        return f"计算结果：{result}"

    except ZeroDivisionError:
        return "错误：除零错误"
    except SyntaxError:
        return "错误：表达式语法错误"
    except Exception as e:
        logger.error(f"计算错误: {e}")
        return f"计算错误：{str(e)}"


@app.tool()
async def text_processor(text: str, operation: str = "upper", **kwargs: Any) -> str:
    """
    高级文本处理工具

    Args:
        text: 要处理的文本
        operation: 操作类型 (upper|lower|title|capitalize|reverse|count|trim|replace)
        **kwargs: 额外参数
            - old_text: 替换操作的源文本
            - new_text: 替换操作的目标文本

    Returns:
        处理后的文本或统计信息
    """
    try:
        if not text:
            return "错误：输入文本为空"

        operation = operation.lower()

        if operation == "upper":
            return text.upper()
        elif operation == "lower":
            return text.lower()
        elif operation == "title":
            return text.title()
        elif operation == "capitalize":
            return text.capitalize()
        elif operation == "reverse":
            return text[::-1]
        elif operation == "count":
            return json.dumps(
                {
                    "字符总数": len(text),
                    "字符数（不含空格）": len(text.replace(" ", "")),
                    "单词数": len(text.split()),
                    "行数": len(text.split("\n")),
                    "段落数": len([p for p in text.split("\n\n") if p.strip()]),
                },
                ensure_ascii=False,
                indent=2,
            )
        elif operation == "trim":
            return text.strip()
        elif operation == "replace":
            old_text = kwargs.get("old_text", "")
            new_text = kwargs.get("new_text", "")
            if not old_text:
                return "错误：替换操作需要提供 old_text 参数"
            return text.replace(old_text, new_text)
        else:
            return f"错误：不支持的操作 '{operation}'。支持的操作：upper, lower, title, capitalize, reverse, count, trim, replace"

    except Exception as e:
        logger.error(f"文本处理错误: {e}")
        return f"处理错误：{str(e)}"


@app.tool()
async def system_info() -> str:
    """
    获取系统信息

    Returns:
        系统信息的 JSON 字符串
    """
    try:
        import platform
        import psutil

        info = {
            "操作系统": platform.system(),
            "操作系统版本": platform.release(),
            "Python版本": platform.python_version(),
            "处理器": platform.processor(),
            "内存信息": {
                "总内存": f"{psutil.virtual_memory().total / (1024**3):.2f} GB",
                "可用内存": f"{psutil.virtual_memory().available / (1024**3):.2f} GB",
                "内存使用率": f"{psutil.virtual_memory().percent}%",
            },
            "磁盘信息": {
                "总空间": f"{psutil.disk_usage('/').total / (1024**3):.2f} GB",
                "可用空间": f"{psutil.disk_usage('/').free / (1024**3):.2f} GB",
                "使用率": f"{(psutil.disk_usage('/').used / psutil.disk_usage('/').total * 100):.2f}%",
            },
            "服务器配置": config.to_dict(),
        }

        return json.dumps(info, ensure_ascii=False, indent=2)

    except ImportError:
        return "系统信息功能需要 psutil 库。请安装：pip install psutil"
    except Exception as e:
        logger.error(f"获取系统信息失败: {e}")
        return f"错误：无法获取系统信息 - {str(e)}"


@app.tool()
async def file_operations(
    operation: str, file_path: str = "", content: str = "", encoding: str = "utf-8"
) -> str:
    """
    安全的文件操作工具

    Args:
        operation: 操作类型 (read|write|append|exists|size|list_dir)
        file_path: 文件路径
        content: 写入内容（仅用于写入操作）
        encoding: 文件编码（默认 utf-8）

    Returns:
        操作结果
    """
    try:
        # 安全检查：限制在当前目录及子目录
        if file_path:
            abs_path = os.path.abspath(file_path)
            current_dir = os.path.abspath(".")
            if not abs_path.startswith(current_dir):
                return "错误：出于安全考虑，只能访问当前目录及其子目录的文件"

        if operation == "read":
            if not file_path:
                return "错误：读取操作需要提供文件路径"
            if not os.path.exists(file_path):
                return f"错误：文件不存在 - {file_path}"

            with open(file_path, "r", encoding=encoding) as f:
                content = f.read()
                # 限制读取大小
                if len(content) > 50000:  # 50KB 限制
                    return f"文件内容过大（{len(content)} 字符），仅显示前50000字符：\n\n{content[:50000]}..."
                return content

        elif operation == "write":
            if not file_path:
                return "错误：写入操作需要提供文件路径"

            # 创建目录（如果不存在）
            os.makedirs(
                os.path.dirname(file_path) if os.path.dirname(file_path) else ".",
                exist_ok=True,
            )

            with open(file_path, "w", encoding=encoding) as f:
                f.write(content)
            return f"成功写入文件：{file_path} ({len(content)} 字符)"

        elif operation == "append":
            if not file_path:
                return "错误：追加操作需要提供文件路径"

            with open(file_path, "a", encoding=encoding) as f:
                f.write(content)
            return f"成功追加到文件：{file_path} ({len(content)} 字符)"

        elif operation == "exists":
            return (
                f"文件{'存在' if os.path.exists(file_path) else '不存在'}：{file_path}"
            )

        elif operation == "size":
            if not os.path.exists(file_path):
                return f"错误：文件不存在 - {file_path}"
            size = os.path.getsize(file_path)
            return f"文件大小：{size} 字节 ({size/1024:.2f} KB)"

        elif operation == "list_dir":
            dir_path = file_path if file_path else "."
            if not os.path.exists(dir_path):
                return f"错误：目录不存在 - {dir_path}"
            if not os.path.isdir(dir_path):
                return f"错误：不是目录 - {dir_path}"

            items = []
            for item in sorted(os.listdir(dir_path)):
                item_path = os.path.join(dir_path, item)
                item_type = "目录" if os.path.isdir(item_path) else "文件"
                items.append(f"{item_type}: {item}")

            return f"目录内容 ({dir_path}):\n" + "\n".join(items)

        else:
            return f"错误：不支持的操作 '{operation}'。支持的操作：read, write, append, exists, size, list_dir"

    except PermissionError:
        return f"错误：没有权限访问文件 - {file_path}"
    except Exception as e:
        logger.error(f"文件操作错误: {e}")
        return f"文件操作错误：{str(e)}"


# ============================================================================
# 资源定义
# ============================================================================


@app.resource("config://server-status")
async def get_server_status() -> str:
    """获取服务器状态信息"""
    try:
        status = {
            "服务器配置": config.to_dict(),
            "运行状态": "正常",
            "可用工具数": len(getattr(app._tool_manager, "_tools", {})),
            "可用资源数": len(getattr(app._resource_manager, "_resources", {})),
            "可用提示数": len(getattr(app._prompt_manager, "_prompts", {})),
            "内存使用": "未知（需要 psutil）",
            "连接状态": "活跃",
        }

        try:
            import psutil

            process = psutil.Process()
            status["内存使用"] = f"{process.memory_info().rss / 1024 / 1024:.2f} MB"
        except ImportError:
            pass

        return json.dumps(status, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"获取服务器状态失败: {e}")
        return f"错误：{str(e)}"


@app.resource("config://capabilities")
async def get_capabilities() -> str:
    """获取服务器能力信息"""
    capabilities = {
        "协议版本": "MCP 1.0",
        "支持的传输": ["stdio", "sse", "streamable-http"],
        "工具功能": {
            "数学计算": "支持基本四则运算和幂运算",
            "文本处理": "支持多种文本操作和统计",
            "时间查询": "支持多种时间格式",
            "系统信息": "获取系统运行状态",
            "文件操作": "安全的文件读写操作",
        },
        "资源功能": {
            "服务器状态": "实时服务器运行状态",
            "能力查询": "服务器功能说明",
            "配置信息": "服务器配置详情",
        },
        "安全特性": {
            "文件访问": "限制在当前目录及子目录",
            "表达式求值": "限制危险字符和函数",
            "内容大小": "限制文件读取大小",
            "路径验证": "防止路径遍历攻击",
        },
    }

    return json.dumps(capabilities, ensure_ascii=False, indent=2)


@app.resource("logs://recent/{count}")
async def get_recent_logs(count: str) -> str:
    """
    获取最近的模拟日志

    Args:
        count: 日志条目数量
    """
    try:
        log_count = int(count)
        if log_count < 1 or log_count > 100:
            return "错误：日志条目数量必须在 1-100 之间"

        logs = []
        for i in range(log_count):
            logs.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "level": ["INFO", "DEBUG", "WARNING"][i % 3],
                    "message": f"模拟日志条目 {i + 1} - 服务器运行正常",
                    "component": "mcp-server",
                    "request_id": f"req-{1000 + i}",
                }
            )

        return json.dumps(
            {"logs": logs, "total": log_count}, ensure_ascii=False, indent=2
        )
    except ValueError:
        return "错误：无效的数字格式"
    except Exception as e:
        return f"错误：{str(e)}"


# ============================================================================
# 提示模板定义
# ============================================================================


@app.prompt()
async def system_analysis(analysis_type: str = "general") -> types.GetPromptResult:
    """
    系统分析提示模板

    Args:
        analysis_type: 分析类型 (general|performance|security|troubleshooting)
    """
    prompts = {
        "general": """请对以下系统信息进行综合分析：

{system_data}

请分析以下方面：
1. 系统整体状态评估
2. 资源使用情况分析
3. 潜在的性能瓶颈
4. 建议的优化措施
5. 风险评估和预警

请提供详细的分析报告和具体的改进建议。""",
        "performance": """请对以下系统性能数据进行专业分析：

{system_data}

重点关注：
1. CPU 使用率和负载模式
2. 内存使用效率和泄漏风险
3. 磁盘 I/O 性能指标
4. 网络吞吐量和延迟
5. 系统瓶颈识别

请提供性能优化建议和调优方案。""",
        "security": """请对以下系统安全状态进行评估：

{system_data}

安全检查项目：
1. 系统漏洞和安全补丁状态
2. 访问控制和权限管理
3. 网络安全配置
4. 日志监控和异常检测
5. 数据保护和备份策略

请提供安全加固建议和风险缓解措施。""",
        "troubleshooting": """请根据以下系统信息进行故障诊断：

{system_data}

故障排查重点：
1. 系统错误和异常分析
2. 服务可用性检查
3. 资源瓶颈定位
4. 配置问题识别
5. 根本原因分析

请提供详细的故障诊断结果和解决方案。""",
    }

    prompt_text = prompts.get(analysis_type, prompts["general"])

    return types.GetPromptResult(
        description=f"系统{analysis_type}分析提示模板",
        messages=[
            types.PromptMessage(
                role="user", content=types.TextContent(type="text", text=prompt_text)
            )
        ],
    )


@app.prompt()
async def data_processing(
    task_type: str = "analysis", data_format: str = "json"
) -> types.GetPromptResult:
    """
    数据处理提示模板

    Args:
        task_type: 任务类型 (analysis|transformation|validation|reporting)
        data_format: 数据格式 (json|csv|xml|text)
    """
    base_prompt = f"""请对以下 {data_format.upper()} 格式的数据执行{task_type}任务：

{{data}}

任务要求："""

    task_requirements = {
        "analysis": """
1. 数据结构和质量分析
2. 统计特征和分布模式
3. 异常值和缺失值检测
4. 数据关联性分析
5. 趋势和模式识别""",
        "transformation": """
1. 数据清洗和标准化
2. 格式转换和结构调整
3. 字段映射和重命名
4. 数据类型转换
5. 衍生字段计算""",
        "validation": """
1. 数据完整性检查
2. 格式规范性验证
3. 业务规则验证
4. 数据一致性检查
5. 质量评分和报告""",
        "reporting": """
1. 数据摘要和统计
2. 可视化建议
3. 关键指标提取
4. 异常情况报告
5. 结论和建议""",
    }

    requirements = task_requirements.get(task_type, task_requirements["analysis"])
    prompt_text = base_prompt + requirements + "\n\n请提供详细的处理结果和专业建议。"

    return types.GetPromptResult(
        description=f"{data_format.upper()} 数据{task_type}提示模板",
        messages=[
            types.PromptMessage(
                role="user", content=types.TextContent(type="text", text=prompt_text)
            )
        ],
    )


# ============================================================================
# 服务器生命周期管理
# ============================================================================


# @app.lifespan()  # 注释掉，因为 FastMCP 可能不支持此装饰器
async def lifespan_context() -> AsyncGenerator[None, None]:
    """服务器生命周期管理"""
    logger.info("🚀 Production MCP Server 启动中...")
    logger.info(f"📋 服务器配置: {config.name} v{config.version}")

    # 启动时初始化
    startup_time = datetime.now()
    logger.info(f"⏰ 启动时间: {startup_time}")

    yield  # 服务器运行期间

    # 关闭时清理
    shutdown_time = datetime.now()
    uptime = shutdown_time - startup_time
    logger.info(f"🛑 Production MCP Server 关闭中...")
    logger.info(f"⏱️ 运行时长: {uptime}")


# ============================================================================
# 命令行接口
# ============================================================================


@click.command()
@click.option(
    "--transport",
    type=click.Choice(["stdio", "sse", "streamable-http"]),
    default="stdio",
    help="传输协议类型",
)
@click.option(
    "--port", type=int, default=8765, help="端口号（仅适用于 sse 和 streamable-http）"
)
@click.option(
    "--host", default="127.0.0.1", help="主机地址（仅适用于 sse 和 streamable-http）"
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    default="INFO",
    help="日志级别",
)
def main(transport: str, port: int, host: str, log_level: str) -> None:
    """启动生产级 MCP 服务器"""

    # 配置日志
    logger.remove()  # 移除默认处理器
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )

    logger.info(f"🎯 启动 {config.name} v{config.version}")
    logger.info(f"📡 传输协议: {transport}")
    logger.info(f"📝 日志级别: {log_level}")

    if transport in ["sse", "streamable-http"]:
        logger.info(f"🌐 服务地址: {host}:{port}")

    # 更新服务器设置
    app.settings.host = host
    app.settings.port = port
    app.settings.log_level = log_level  # type: ignore[assignment]

    try:
        # 启动服务器
        logger.info("✅ 服务器启动完成，等待客户端连接...")
        app.run(transport=transport)  # type: ignore[arg-type]
    except KeyboardInterrupt:
        logger.info("🛑 收到中断信号，正在关闭服务器...")
    except Exception as e:
        logger.error(f"❌ 服务器启动失败: {e}")
        raise
    finally:
        logger.info("👋 服务器已关闭")


if __name__ == "__main__":
    main()
