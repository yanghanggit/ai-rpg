"""守卫 ``Entity.add`` 的使用位置。

entitas 是底层库，本身不感知上层游戏；「``add`` 只在实体创建阶段使用」是**上层
项目**的约定，因此约束放在 ``tests/`` 而不是 entitas 内部：

- 仅 ``src/ai_rpg/game/dbg_game.py`` 中以 ``create`` / ``_create`` 开头的函数；
- ``tests/`` 下全部代码。

运行期（systems / services / pipelines）必须使用 ``Entity.replace``：它同时承担
「新增」与「替换」语义，避免「先 has 再 add」的分支。

检测方式（AST）：扫描 ``src/``、``demo/``，凡方法名为 ``add``（或内部原语
``_add``）且**首个位置参数是组件类**的调用即视为 ``Entity.add``。容器调用
（``processors.add(System(...))``、``seen.add(name)``、``db.add(obj)`` 等）的首个
参数不是组件类，不会误报。
"""

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final, List, Optional

ROOT: Final = Path(__file__).resolve().parents[2]

#: 需要扫描的上层代码目录（tests/ 本身就是豁免区，无需扫描）。
SCAN_DIRS: Final = ("src", "demo")

#: 允许调用 add 的唯一模块。
DBG_GAME_PATH: Final = ROOT / "src" / "ai_rpg" / "game" / "dbg_game.py"

#: 模块内允许调用 add 的函数名前缀。
CREATE_FUNC_PATTERN: Final = re.compile(r"^_?create")

#: 被守护的方法名：公开创建期 API 及其内部原语。
GUARDED_METHODS: Final = frozenset({"add", "_add"})


@dataclass(frozen=True)
class Violation:
    """一处非法的 ``Entity.add`` 调用。"""

    path: Path
    line: int
    function: str

    def format(self) -> str:
        try:
            rel_path: Path = self.path.relative_to(ROOT)
        except ValueError:
            rel_path = self.path
        return f"{rel_path}:{self.line}: 在 `{self.function or '<module>'}` 中调用了 Entity.add/_add"


def _root_name(node: ast.expr) -> Optional[str]:
    """返回 ``Name`` / ``Attribute`` 链最左侧的名字。"""
    current: ast.expr = node
    while isinstance(current, ast.Attribute):
        current = current.value
    if isinstance(current, ast.Name):
        return current.id
    return None


def _looks_like_component_type(node: ast.expr) -> bool:
    """判断首个位置参数是否「像一个组件类」。

    只认首字母大写的名字、属性访问链或它们的下标（例如 ``CardComponent``、
    ``models.CardComponent``）。容器类的 add 通常传实例、字符串或小写变量，
    因此不会命中。
    """
    if isinstance(node, ast.Subscript):
        return _looks_like_component_type(node.value)
    root = _root_name(node)
    return root is not None and root[:1].isupper()


class _AddUsageChecker(ast.NodeVisitor):
    """遍历单个文件，收集非法的 ``Entity.add`` 调用。"""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._func_stack: List[str] = []
        self.violations: List[Violation] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._func_stack.append(node.name)
        self.generic_visit(node)
        self._func_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._func_stack.append(node.name)
        self.generic_visit(node)
        self._func_stack.pop()

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr in GUARDED_METHODS
            and node.args
            and _looks_like_component_type(node.args[0])
            and not self._allowed_here()
        ):
            self.violations.append(
                Violation(
                    path=self._path,
                    line=node.lineno,
                    function=self._func_stack[-1] if self._func_stack else "",
                )
            )

        self.generic_visit(node)

    def _allowed_here(self) -> bool:
        if self._path.resolve() != DBG_GAME_PATH.resolve():
            return False
        function = self._func_stack[-1] if self._func_stack else ""
        return CREATE_FUNC_PATTERN.match(function) is not None


def _check_source(source: str, path: Path) -> List[Violation]:
    checker = _AddUsageChecker(path)
    checker.visit(ast.parse(source, filename=str(path)))
    return checker.violations


def _check_file(path: Path) -> List[Violation]:
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError) as exc:
        raise AssertionError(f"无法解析文件 {path}: {exc}") from exc

    checker = _AddUsageChecker(path)
    checker.visit(tree)
    return checker.violations


def _find_violations() -> List[Violation]:
    violations: List[Violation] = []
    for dirname in SCAN_DIRS:
        for path in sorted((ROOT / dirname).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            violations.extend(_check_file(path))
    return violations


def test_entity_add_only_used_during_entity_creation() -> None:
    violations = _find_violations()
    assert (
        not violations
    ), "以下位置非法使用了 Entity.add，运行期请改用 Entity.replace:\n" + "\n".join(
        v.format() for v in violations
    )


def test_checker_flags_add_in_runtime_system() -> None:
    """自检：运行期模块中的 entity.add 必须被检出。"""
    source = """
def react(self, entities):
    entity = entities[0]
    entity.add(EquippedGearComponent, entity.name, [])
"""
    path = ROOT / "src" / "ai_rpg" / "systems" / "fake_system.py"
    assert [(v.function, v.line) for v in _check_source(source, path)] == [("react", 4)]


def test_checker_flags_private_add_in_runtime_module() -> None:
    """自检：绕道 ``_add`` 也会被检出。"""
    source = """
def react(self, entity):
    entity._add(ActorComponent, "name", "")
"""
    path = ROOT / "src" / "ai_rpg" / "systems" / "fake_system.py"
    assert [(v.function, v.line) for v in _check_source(source, path)] == [("react", 3)]


def test_checker_allows_add_in_dbg_game_create_function() -> None:
    """自检：dbg_game.py 的 create_* / _create_* 函数允许 add。"""
    source = """
def create_actor_entities(self, actor_models):
    entity.add(ActorComponent, "name", "")

def _create_world_entities(self, world_models):
    entity.add(WorldComponent, "world")

def build_from_blueprint(self):
    entity.add(WorldComponent, "world")
"""
    violations = _check_source(source, DBG_GAME_PATH)
    assert [(v.function, v.line) for v in violations] == [("build_from_blueprint", 9)]


def test_checker_ignores_container_add_calls() -> None:
    """自检：容器 / 集合的 add 不能被误报。"""
    source = """
def build(processors, seen, db, entities):
    processors.add(PrologueSystem(None))
    seen.add("name")
    db.add(document)
    entities.add(entity)
"""
    path = ROOT / "src" / "ai_rpg" / "systems" / "fake_system.py"
    assert _check_source(source, path) == []
