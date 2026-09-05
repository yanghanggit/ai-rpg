"""Procrastinate 任务队列应用实例"""

import procrastinate
from .config import postgresql_config

# 全局单例：所有后台任务通过 @procrastinate_app.task 装饰并注册到此处
procrastinate_app = procrastinate.App(
    connector=procrastinate.PsycopgConnector(
        conninfo=postgresql_config.connection_string
    )
)
