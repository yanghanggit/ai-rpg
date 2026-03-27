# -*- mode: python ; coding: utf-8 -*-
# packaging/game_client.spec
#
# PyInstaller spec for AI RPG TUI Game Client (macOS)
#
# 构建方法（在项目根目录）：
#   make client-build
#
# 或手动构建：
#   cd packaging && uv run pyinstaller game_client.spec --distpath ../dist/client --workpath ../build/client

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

PROJECT_ROOT = Path(SPECPATH).parent                    # ai-rpg/
SCRIPT     = str(PROJECT_ROOT / "scripts" / "run_tui_game_client.py")

block_cipher = None

a = Analysis(
    [SCRIPT],
    pathex=[str(PROJECT_ROOT / "scripts")],
    binaries=[],
    datas=[],
    hiddenimports=[
        # Textual 内部动态加载的模块
        "textual",
        "textual.app",
        "textual.widget",
        "textual.widgets",
        "textual.widgets._header",
        "textual.widgets._footer",
        "textual.widgets._input",
        "textual.widgets._static",
        "textual.widgets._rich_log",
        "textual.containers",
        "textual.screen",
        "textual.css",
        "textual.css.stylesheet",
        "textual.css.styles",
        "textual.css.model",
        "textual.css.scalar",
        "textual.css.constants",
        "textual.css.tokenizer",
        "textual.css.parse",
        "textual.css.query",
        "textual.css.errors",
        "textual.css.types",
        "textual.css.transition",
        "textual._on",
        "textual.binding",
        "textual.reactive",
        "textual.message",
        "textual.events",
        "textual.driver",
        "textual.drivers",
        "textual.drivers._xterm_driver",
        "textual.theme",
        "textual.design",
        "textual.color",
        "textual.visual",
        "textual.strip",
        "textual.geometry",
        "textual.layout",
        "textual.layouts",
        "textual.renderables",
        "textual.suggest",
        "textual.suggester",
        "textual.validation",
        # click
        "click",
        # Rich (Textual 依赖)
        "rich",
        "rich.console",
        "rich.markup",
        "rich.text",
        "rich.style",
        "rich.segment",
        "rich.highlighter",
        # httpx (预留 API 调用)
        "httpx",
        "httpcore",
        "anyio",
        "anyio._backends._asyncio",
        # ai_rpg 内部模块（collect_submodules 递归收集，新增 Screen 无需手动维护）
        *collect_submodules("ai_rpg.tui_client"),
        *collect_submodules("ai_rpg.models"),
        # 标准库可能被 PyInstaller 漏掉的
        "asyncio",
        "signal",
        "select",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 明确排除主项目的重型依赖
        "torch",
        "chromadb",
        "langchain",
        "langgraph",
        "fastapi",
        "uvicorn",
        "sqlalchemy",
        "pandas",
        "numpy",
        "openai",
        "tiktoken",
        "sentence_transformers",
        "replicate",
        "textual_serve",
        "aiohttp_jinja2",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="game_client",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,   # 必须保留 console=True，Textual 需要终端
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
