"""维护脚本包（`python -m scripts.<name>` 入口）。

显式包标记：让 mypy 把 `scripts/<name>.py` 识别为 `scripts.<name>`，
与 `demo/__init__.py` 同理，避免同一文件被映射成两个模块名。
"""
