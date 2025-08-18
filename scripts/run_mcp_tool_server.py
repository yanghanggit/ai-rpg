#!/usr/bin/env python3
"""
MCP 工具服务器

基于 FastAPI 的 Model Context Protocol (MCP) 工具服务器实现。
提供标准化的工具调用接口，支持通过 HTTP 协议与客户端通信。

功能：
1. 提供 MCP 标准协议端点
2. 管理工具注册和执行
3. 支持工具发现和元数据查询
4. 提供详细的错误处理和日志记录

启动方式：
    python scripts/mcp_tool_server.py

API 端点：
    GET /tools - 获取所有可用工具
    POST /tools/{tool_name}/call - 执行指定工具
    GET /tools/{tool_name} - 获取工具详细信息
    GET /health - 健康检查
"""

import os
import sys
import traceback

# 将 src 目录添加到模块搜索路径
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

import asyncio
import json
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pydantic import BaseModel, Field

# MCP 相关类型定义
from mcp.types import Tool


# ============================================================================
# 数据模型定义
# ============================================================================

class ToolCallRequest(BaseModel):
    """工具调用请求模型"""
    arguments: Dict[str, Any] = Field(default_factory=dict, description="工具调用参数")


class ToolCallResponse(BaseModel):
    """工具调用响应模型"""
    success: bool = Field(description="调用是否成功")
    result: Any = Field(description="工具执行结果")
    error: Optional[str] = Field(default=None, description="错误信息")
    execution_time: float = Field(description="执行时间（秒）")


class ToolInfo(BaseModel):
    """工具信息模型"""
    name: str = Field(description="工具名称")
    description: str = Field(description="工具描述")
    input_schema: Dict[str, Any] = Field(description="输入参数schema")


class ServerStatus(BaseModel):
    """服务器状态模型"""
    status: str = Field(description="服务器状态")
    version: str = Field(description="服务器版本")
    available_tools: int = Field(description="可用工具数量")
    uptime: str = Field(description="运行时间")


# ============================================================================
# 工具实现
# ============================================================================

class McpToolRegistry:
    """MCP 工具注册表"""
    
    def __init__(self):
        self.tools: Dict[str, Dict[str, Any]] = {}
        self.start_time = datetime.now()
        self._register_builtin_tools()
    
    def _register_builtin_tools(self):
        """注册内置工具"""
        self.register_tool(
            name="get_current_time",
            description="获取当前系统时间",
            input_schema={
                "type": "object",
                "properties": {},
                "required": []
            },
            function=self._get_current_time
        )
        
        self.register_tool(
            name="calculator",
            description="执行数学计算",
            input_schema={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "数学表达式，如 '2+3*4'"
                    }
                },
                "required": ["expression"]
            },
            function=self._calculator
        )
        
        self.register_tool(
            name="text_processor",
            description="处理文本内容",
            input_schema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "要处理的文本"
                    },
                    "operation": {
                        "type": "string",
                        "description": "操作类型：upper/lower/reverse/count",
                        "default": "upper"
                    }
                },
                "required": ["text"]
            },
            function=self._text_processor
        )
    
    def register_tool(self, name: str, description: str, input_schema: Dict[str, Any], function):
        """注册工具"""
        tool = Tool(
            name=name,
            description=description,
            inputSchema=input_schema
        )
        
        self.tools[name] = {
            "tool": tool,
            "function": function
        }
        logger.info(f"工具已注册: {name}")
    
    def get_tool_list(self) -> List[ToolInfo]:
        """获取工具列表"""
        tools = []
        for name, tool_data in self.tools.items():
            tool = tool_data["tool"]
            tools.append(ToolInfo(
                name=tool.name,
                description=tool.description,
                input_schema=tool.inputSchema or {}
            ))
        return tools
    
    def get_tool_info(self, tool_name: str) -> Optional[ToolInfo]:
        """获取工具信息"""
        if tool_name not in self.tools:
            return None
        
        tool = self.tools[tool_name]["tool"]
        return ToolInfo(
            name=tool.name,
            description=tool.description,
            input_schema=tool.inputSchema or {}
        )
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolCallResponse:
        """调用工具"""
        start_time = datetime.now()
        
        try:
            if tool_name not in self.tools:
                raise ValueError(f"工具 '{tool_name}' 不存在")
            
            tool_function = self.tools[tool_name]["function"]
            
            # 执行工具函数
            if asyncio.iscoroutinefunction(tool_function):
                result = await tool_function(**arguments)
            else:
                result = tool_function(**arguments)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"工具调用成功: {tool_name} | 参数: {arguments} | 结果: {result}")
            
            return ToolCallResponse(
                success=True,
                result=result,
                execution_time=execution_time
            )
        
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            error_msg = f"工具执行失败: {str(e)}"
            
            logger.error(f"工具调用失败: {tool_name} | 参数: {arguments} | 错误: {error_msg}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            
            return ToolCallResponse(
                success=False,
                result=None,
                error=error_msg,
                execution_time=execution_time
            )
    
    def get_server_status(self) -> ServerStatus:
        """获取服务器状态"""
        uptime = datetime.now() - self.start_time
        return ServerStatus(
            status="running",
            version="1.0.0",
            available_tools=len(self.tools),
            uptime=str(uptime)
        )
    
    # ========================================================================
    # 内置工具实现
    # ========================================================================
    
    def _get_current_time(self) -> str:
        """获取当前时间"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def _calculator(self, expression: str) -> str:
        """安全的计算器工具"""
        try:
            # 安全的数学表达式求值（仅允许数字和基本运算符）
            allowed_chars = set("0123456789+-*/.() ")
            if not all(c in allowed_chars for c in expression):
                return "错误：表达式包含不允许的字符"
            
            result = eval(expression)
            return f"计算结果：{result}"
        except Exception as e:
            return f"计算错误：{str(e)}"
    
    def _text_processor(self, text: str, operation: str = "upper") -> str:
        """文本处理工具"""
        try:
            if operation == "upper":
                return text.upper()
            elif operation == "lower":
                return text.lower()
            elif operation == "reverse":
                return text[::-1]
            elif operation == "count":
                return f"字符数：{len(text)}"
            else:
                return f"不支持的操作：{operation}"
        except Exception as e:
            return f"处理错误：{str(e)}"


# ============================================================================
# FastAPI 应用初始化
# ============================================================================

app = FastAPI(
    title="MCP 工具服务器",
    description="Model Context Protocol (MCP) 工具服务器",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化工具注册表
tool_registry = McpToolRegistry()


# ============================================================================
# API 端点
# ============================================================================

@app.get("/health", response_model=ServerStatus)
async def health_check():
    """健康检查"""
    return tool_registry.get_server_status()


@app.get("/tools", response_model=List[ToolInfo])
async def get_tools():
    """获取所有可用工具"""
    return tool_registry.get_tool_list()


@app.get("/tools/{tool_name}", response_model=ToolInfo)
async def get_tool_info(tool_name: str):
    """获取指定工具的详细信息"""
    tool_info = tool_registry.get_tool_info(tool_name)
    if not tool_info:
        raise HTTPException(status_code=404, detail=f"工具 '{tool_name}' 不存在")
    return tool_info


@app.post("/tools/{tool_name}/call", response_model=ToolCallResponse)
async def call_tool(tool_name: str, request: ToolCallRequest):
    """调用指定工具"""
    return await tool_registry.call_tool(tool_name, request.arguments)


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "MCP 工具服务器",
        "version": "1.0.0",
        "docs": "/docs",
        "tools": "/tools"
    }


# ============================================================================
# 服务器启动
# ============================================================================

def main():
    """启动 MCP 工具服务器"""
    logger.info("🚀 启动 MCP 工具服务器...")
    
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8765,
        reload=False,  # 禁用 reload 避免模块导入问题
        log_level="info"
    )


if __name__ == "__main__":
    main()
