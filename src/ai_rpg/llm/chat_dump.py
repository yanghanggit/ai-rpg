"""chat dump：把一次对话 client 每轮的完整对话落盘到 `.chat_dumps/` 下的文本文件。

调试用途的旁路能力，从通讯层主流程里抽出来单独存放，避免调试代码污染请求路径。
依赖类型是 `ChatClientProtocol` 而非具体实现，只读公共成员，因此本模块
**不得** import `ai_rpg.deepseek`。

落盘要同时满足两级开关（AND 关系，后者是前者的上限）：

1. **实例级**：client 的构造参数 `dump`（默认 True）——「我想不想留痕」。
   单测 / 压测 / 批量任务可以只关自己这一批，不影响别人。
2. **进程级**：环境变量 ``AI_RPG_CHAT_DUMP_ENABLED``（默认 True）——「这台进程
   允不允许落盘」。生产部署在 `.env` 里置 false 即可整体关掉，不用改代码，
   也压得住任何忘记传 `dump=False` 的调用方。

`client.dump=True` 但进程级被关闭时，本模块会**只警告一次**再跳过：静默失效
比落盘更糟。两级判断都收敛在 `dump_chat` 里，provider 的 `chat()` 无需重复判断。

进程级开关必须**调用时**读取，不能做模块级快照：`load_dotenv()` 在
`deepseek/client.py` 的 import 期执行，而本模块比它更早被导入，快照会读到
.env 加载前的值。

目录在**写入时**才创建：抽象层不在 import 期产生文件系统副作用。
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Final, List

from loguru import logger

from ..models import AIMessage, ChatMessage, HumanMessage, get_buffer_string
from .protocol import ChatClientProtocol

############################################################################################################
# chat dump 存储目录（项目根目录下）；首次 dump 时创建
CHAT_DUMP_DIR: Path = Path(".chat_dumps")

_SEP = "-" * 86

# 进程级总开关（.env / 环境变量）；未设置视为开启，仅显式的假值才关闭
ENV_DUMP_SWITCH: Final[str] = "AI_RPG_CHAT_DUMP_ENABLED"

# 判定为「关闭」的取值（大小写不敏感、去空白后比较）；其余一律视为开启
_FALSE_VALUES: Final[frozenset[str]] = frozenset({"0", "false", "no", "off"})

# 「进程级关闭导致 dump 请求被忽略」只警告一次，避免每次 LLM 调用刷屏
_warned_env_suppressed: bool = False

# 文件名安全字符集：中文、字母、数字与 _ - .；其余（含 | : / \ 空格 等）替换为下划线
_SAFE_FILENAME_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"[^0-9A-Za-z_\-.\u4e00-\u9fff]"
)


############################################################################################################
def env_allows_dump() -> bool:
    """进程级总开关是否允许落盘（默认允许）。

    每次调用都读环境变量：`load_dotenv()` 晚于本模块导入，模块级快照会过期。
    """
    raw = os.getenv(ENV_DUMP_SWITCH)
    if raw is None:
        return True
    return raw.strip().lower() not in _FALSE_VALUES


############################################################################################################
def _warn_env_suppressed() -> None:
    """「实例想开、进程级关了」只警告一次。"""
    global _warned_env_suppressed
    if _warned_env_suppressed:
        return
    _warned_env_suppressed = True
    reason = f"chat dump 已被环境变量 {ENV_DUMP_SWITCH} 关闭"
    logger.warning(f"{reason}；client.dump=True 被忽略（本进程不再落盘，仅提示一次）")


############################################################################################################
def dump_chat(client: ChatClientProtocol) -> None:
    """将 client 本轮的完整对话写入 .chat_dumps/ 下的文本文件。

    只使用协议暴露的公共成员（label / input_message / messages /
    response_ai_message / response_reasoning_content / dump），不触碰实现私有字段，
    因此对任何 `ChatClientProtocol` 实现都适用。

    两级开关（AND）：`client.dump`（实例级）与 ``AI_RPG_CHAT_DUMP_ENABLED``
    （进程级上限）都为真才落盘；进程级关闭而实例想开时警告一次。
    落盘失败只记 warning（调试旁路不能影响主流程）。
    """

    # 调用方（provider 的 chat()）无需重复判断是否该落盘，策略只在这里。
    if not client.dump:
        return
    if not env_allows_dump():
        _warn_env_suppressed()
        return

    try:

        # 拷贝 messages，再把本轮 prompt / response 分别补齐，
        # 使全部消息（含本轮）统一交给 get_buffer_string.
        messages: List[ChatMessage] = list(client.messages)

        # 仅在 prompt 非空时追加本轮 prompt：continuation 模式下 prompt 为空，
        # 不应产生一条幽灵空 Human 消息。
        if client.input_message:
            messages.append(HumanMessage(content=client.input_message))

        # 追加本轮 response：优先用原始 AIMessage（保留 tool_calls 等 additional_kwargs）；
        # 仅当响应缺失（如 200 但空 choices）时才退化为纯文本。
        if client.response_ai_message is not None:
            messages.append(client.response_ai_message)
        else:
            messages.append(AIMessage(content=client.response_content))

        # 提取对话内容为字符串，带有分隔符和角色标记；
        # chat dump 用于调试，需渲染 tool_calls（否则工具调用显示为空 AI:）。
        content = get_buffer_string(
            messages,
            system_prefix="\n" + _SEP + "\nSystem",
            human_prefix="\n" + _SEP + "\nHuman",
            ai_prefix="\n" + _SEP + "\nAI",
            tool_prefix="\n" + _SEP + "\nTool",
            render_tool_calls=True,
        )

        # Reasoning（可选）
        if client.response_reasoning_content:
            content += "\n" + _SEP + "\n" + client.response_reasoning_content

        # 内容结束。
        content += "\n"

        # 写入文件，文件名格式为：YYYYMMDD_HHMMSS_microseconds_label.txt
        # label 可能带「主体|服务对象」这类分隔标记（如外观合成），且含路径分隔符/冒号等
        # 会破坏文件名的字符；统一把非 [中文 字母 数字 _ - .] 的字符换成 "_"。
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        safe_label = _SAFE_FILENAME_PATTERN.sub("_", client.label)
        dump_file = CHAT_DUMP_DIR / f"{timestamp}_{safe_label}.txt"
        CHAT_DUMP_DIR.mkdir(parents=True, exist_ok=True)
        dump_file.write_text(content, encoding="utf-8")
        logger.debug(f"chat dump saved: {dump_file}")

    except Exception as e:

        logger.warning(
            f"dump_chat failed for '{client.label}': {type(e).__name__}: {e}"
        )


__all__ = ["CHAT_DUMP_DIR", "ENV_DUMP_SWITCH", "dump_chat", "env_allows_dump"]
