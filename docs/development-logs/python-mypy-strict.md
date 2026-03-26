# Python mypy strict 模式注意事项

本项目使用 `mypy --strict` 静态类型检查，以下是开发过程中收集的常见问题与解决方案。

---

## 1. 包内导入必须使用相对导入

`mypy --strict` 下，**同一包内**的模块互相导入必须使用相对导入，不能使用绝对路径。

```python
# ❌ 错误：mypy 会报模块解析错误
from ai_rpg.tui_client.server_client import login, new_game
from ai_rpg.tui_client.screens.new_game import NewGameScreen

# ✅ 正确：使用相对导入
from ..server_client import login, new_game   # 上一级
from .new_game import NewGameScreen           # 同级
```

**规则**：

- 绝对导入仅用于**跨包**（第三方库、`src/` 下不同顶层包之间）
- 同一包/子包内部一律用相对导入（`.` 同级，`..` 上一级）

---

## 2. httpx / requests response.json() 返回 Any，需要 cast

`httpx.Response.json()` 和 `requests.Response.json()` 返回类型为 `Any`，直接 return 会触发：

```text
error: Returning Any from function declared to return "dict[str, Any]"  [no-any-return]
```

**解决方案**：

```python
from typing import Any, Dict, cast
import httpx

async def fetch_data() -> Dict[str, Any]:
    async with httpx.AsyncClient() as client:
        response = await client.get("http://...")
        response.raise_for_status()
        return cast(Dict[str, Any], response.json())  # ✅ 用 cast 显式标注
```

---

## 3. 常用 mypy 命令

```bash
# 检查整个 src/
uv run mypy --strict src/

# 检查 scripts/
uv run mypy --strict scripts/

# 合并执行（同 make lint）
make lint
```
