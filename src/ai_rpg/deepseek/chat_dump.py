"""兼容出口：chat dump 已搬到 `ai_rpg.llm.chat_dump`。

真实实现在 `ai_rpg.llm.chat_dump`。是否落盘由 client 的构造参数 `dump`
（默认 True）决定，本模块不再有全局开关，因此这里只做纯转发，没有状态需要同步。
"""

from ..llm.chat_dump import CHAT_DUMP_DIR, dump_chat

__all__ = ["CHAT_DUMP_DIR", "dump_chat"]
