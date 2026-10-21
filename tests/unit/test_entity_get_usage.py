"""守卫「``Entity.get`` 之后不得就地修改」。

上层约定：运行期对组件的写入必须走 ``Entity.replace``（它才会发出
``on_component_replaced`` 并被 ECS 观察到）。``Entity.get`` 只用于读取；
拿到组件后直接改字段、改列表、改嵌套对象都属于隐式写入，本测试负责拦截。

检测方式（AST）：

- ``x = entity.get(Xxx)`` / ``x = entity.get(Xxx).attr`` 后对 ``x`` 做
  字段赋值、切片赋值、``append/extend/clear/pop/remove/...``、``shuffle`` 等；
- 直接链式 ``entity.get(Xxx).cards.append(...)``；
- 通过「返回组件内部活引用」的模块内辅助函数（如 ``_pile_cards``、
  ``read_pile_cards``）拿到的列表再做同样的事。

``tests/`` 整体豁免：测试需要直接构造与篡改组件状态。
现有运行期违规登记在 :data:`GRANDFATHERED`（按 ``(文件, 函数)`` 记录），
只允许减少：修复后请从集合里删除对应条目。
"""

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Final, FrozenSet, List, Optional, Set, Tuple

ROOT: Final = Path(__file__).resolve().parents[2]

#: 需要扫描的运行期代码目录（tests/ 豁免）。
SCAN_DIRS: Final = ("src", "demo")

#: 会就地修改容器的列表方法。
MUTATING_METHODS: Final = frozenset(
    {
        "append",
        "extend",
        "insert",
        "pop",
        "remove",
        "clear",
        "sort",
        "reverse",
        "update",
        "add",
        "discard",
        "popitem",
        "setdefault",
    }
)

#: 会就地修改入参的自由函数 / 模块函数。
MUTATING_FUNCTIONS: Final = frozenset({"shuffle", "sort"})

#: 既有违规 `(相对路径, 函数名)`。只允许减少，不允许新增。
GRANDFATHERED: Final[FrozenSet[Tuple[str, str]]] = frozenset()

#: ``root`` 为「直接 get 链」时的哨兵值。
_DIRECT: Final = "\0direct"

#: ``root`` 为「provider 辅助函数」时的哨兵值。
_PROVIDER: Final = "\0provider"


@dataclass(frozen=True)
class Violation:
    """一处 get 之后就地的隐式写入。"""

    rel_path: str
    function: str
    line: int
    expr: str

    @property
    def key(self) -> Tuple[str, str]:
        return (self.rel_path, self.function)

    def format(self) -> str:
        function = self.function or "<module>"
        return f"{self.rel_path}:{self.line} ({function}): {self.expr}"


def _is_entity_get(node: ast.expr) -> bool:
    """判断是否是 ``something.get(XxxComponent)`` 形态。"""
    if not (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and node.args
    ):
        return False
    arg = node.args[0]
    if isinstance(arg, ast.Name):
        return arg.id[:1].isupper()
    if isinstance(arg, ast.Attribute):
        return arg.attr[:1].isupper()
    return False


def _names_target(target: ast.expr) -> List[str]:
    """赋值目标里的简单名字（支持解包）。"""
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        names: List[str] = []
        for element in target.elts:
            names.extend(_names_target(element))
        return names
    return []


def _root_name(node: ast.expr, providers: Dict[str, int]) -> Optional[str]:
    """取表达式的「根」：名字 / 直接 get 链 / provider 调用。"""
    current = node
    while True:
        if isinstance(current, ast.Attribute):
            current = current.value
        elif isinstance(current, ast.Subscript):
            current = current.value
        elif isinstance(current, ast.Call):
            if _is_entity_get(current):
                return _DIRECT
            if isinstance(current.func, ast.Name) and current.func.id in providers:
                return _PROVIDER
            current = current.func
        else:
            break
    if isinstance(current, ast.Name):
        return current.id
    return None


def _is_live_value(node: ast.expr, providers: Dict[str, int]) -> bool:
    """表达式是否是 get 链 / provider 返回的活引用（可能带属性、下标）。"""
    root = _root_name(node, providers)
    return root in (_DIRECT, _PROVIDER)


def _plain_root_name(node: ast.expr) -> Optional[str]:
    """只沿属性 / 下标回溯到名字；遇到函数调用就放弃。

    别名传播必须走这条路径：``cards = deck.cards.copy()`` 得到的是新列表，
    不应被视为组件内部活引用的别名。
    """
    current = node
    while isinstance(current, (ast.Attribute, ast.Subscript)):
        current = current.value
    if isinstance(current, ast.Name):
        return current.id
    return None


def _tracked_names(fn: ast.AST, providers: Dict[str, int]) -> Dict[str, str]:
    """收集函数内「当前持有组件活引用」的局部名字。

    按行号顺序模拟赋值：``x = entity.get(X)`` 记为活引用；``x = y.cards``
    继承别名；``x = y.model_copy()`` 这类会脱离活引用的赋值则把 ``x`` 取消跟踪。
    ``for x in <活引用>`` 的循环变量也按元素活引用处理。
    """
    statements = [
        node
        for node in ast.walk(fn)
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.For, ast.AsyncFor))
    ]
    tracked: Dict[str, str] = {}

    for statement in sorted(statements, key=lambda node: node.lineno):
        if isinstance(statement, (ast.Assign, ast.AnnAssign)):
            value = statement.value
            targets = (
                statement.targets
                if isinstance(statement, ast.Assign)
                else [statement.target]
            )
            names = [name for target in targets for name in _names_target(target)]

            alias_root = _plain_root_name(value) if value is not None else None
            live = value is not None and _is_live_value(value, providers)
            if live:
                assert value is not None
                source = ast.unparse(value)
            elif alias_root is not None and alias_root in tracked:
                source = tracked[alias_root]
            else:
                for name in names:
                    tracked.pop(name, None)
                continue

            for name in names:
                tracked[name] = source
        else:
            names = _names_target(statement.target)
            if _iter_is_live(statement.iter, tracked, providers):
                for name in names:
                    tracked[name] = f"<element of {ast.unparse(statement.iter)}>"
            else:
                for name in names:
                    tracked.pop(name, None)

    return tracked


def _return_is_live(
    value: ast.expr, tracked: Dict[str, str], providers: Dict[str, int]
) -> bool:
    """返回值是否把组件内部活引用（或其元素）直接交给了调用方。"""
    if _is_live_value(value, providers):
        return True
    if isinstance(value, (ast.Tuple, ast.List, ast.Set)):
        return any(
            _return_is_live(element, tracked, providers) for element in value.elts
        )
    if isinstance(value, ast.Dict):
        return any(
            item is not None and _return_is_live(item, tracked, providers)
            for item in value.values
        )
    root = _plain_root_name(value)
    return root is not None and root in tracked


def _iter_is_live(
    node: ast.expr, tracked: Dict[str, str], providers: Dict[str, int]
) -> bool:
    """``for x in <活引用>``（含 enumerate/zip 等包装）的元素也是活引用。"""
    root = _root_name(node, providers)
    if root in (_DIRECT, _PROVIDER):
        return True
    if root is not None and root in tracked:
        return True
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"enumerate", "zip", "sorted", "reversed", "list", "tuple"}
    ):
        return any(
            _iter_is_live(argument, tracked, providers) for argument in node.args
        )
    return False


def _module_providers(tree: ast.AST) -> Dict[str, int]:
    """找出「返回组件内部活引用」的模块内函数（如 ``_pile_cards``）。"""
    functions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    providers: Dict[str, int] = {}
    changed = True
    while changed:
        changed = False
        for function in functions:
            if function.name in providers:
                continue
            tracked = _tracked_names(function, providers)
            for node in ast.walk(function):
                if not isinstance(node, ast.Return) or node.value is None:
                    continue
                if _return_is_live(node.value, tracked, providers):
                    providers[function.name] = node.lineno
                    changed = True
                    break
    return providers


def _mutation(
    statement: ast.stmt, tracked: Dict[str, str], providers: Dict[str, int]
) -> Optional[str]:
    """若 statement 就地修改了 tracked 里的组件 / 活引用，返回描述。"""
    core = statement.value if isinstance(statement, ast.Expr) else statement

    if isinstance(statement, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
        targets = (
            statement.targets
            if isinstance(statement, ast.Assign)
            else [statement.target]
        )
        for target in targets:
            if isinstance(target, ast.Name):
                continue
            root = _root_name(target, providers)
            if root in (_DIRECT, _PROVIDER) or (root is not None and root in tracked):
                return ast.unparse(statement)

    if isinstance(statement, ast.Delete):
        for target in statement.targets:
            root = _root_name(target, providers)
            if root in (_DIRECT, _PROVIDER) or (root is not None and root in tracked):
                return ast.unparse(statement)

    if isinstance(core, ast.Call):
        if isinstance(core.func, ast.Attribute) and core.func.attr in MUTATING_METHODS:
            root = _root_name(core.func.value, providers)
            if root in (_DIRECT, _PROVIDER) or (root is not None and root in tracked):
                return ast.unparse(statement)

        func_name: Optional[str] = None
        if isinstance(core.func, ast.Name):
            func_name = core.func.id
        elif isinstance(core.func, ast.Attribute):
            func_name = core.func.attr
        if func_name in MUTATING_FUNCTIONS:
            for argument in core.args:
                root = _root_name(argument, providers)
                if root in (_DIRECT, _PROVIDER) or (
                    root is not None and root in tracked
                ):
                    return ast.unparse(statement)

    return None


def _scan_function(
    rel_path: str,
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    providers: Dict[str, int],
) -> List[Violation]:
    tracked = _tracked_names(function, providers)
    violations: List[Violation] = []
    for statement in ast.walk(function):
        if not isinstance(statement, ast.stmt):
            continue
        expr = _mutation(statement, tracked, providers)
        if expr is not None:
            violations.append(
                Violation(
                    rel_path=rel_path,
                    function=function.name,
                    line=statement.lineno,
                    expr=expr,
                )
            )
    return violations


def _check_tree(rel_path: str, tree: ast.AST) -> List[Violation]:
    providers = _module_providers(tree)
    violations: List[Violation] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            violations.extend(_scan_function(rel_path, node, providers))

    # 同一函数被嵌套遍历时可能重复，按 (function, line, expr) 去重
    unique: Dict[Tuple[str, int, str], Violation] = {}
    for violation in violations:
        unique[(violation.function, violation.line, violation.expr)] = violation
    return list(unique.values())


def _check_source(source: str, rel_path: str) -> List[Violation]:
    """对给定源码运行检查（供自测使用）。"""
    return _check_tree(rel_path, ast.parse(source))


def _rel_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _is_test_file(rel_path: str) -> bool:
    return rel_path == "tests" or rel_path.startswith("tests/")


def _check_file(path: Path) -> List[Violation]:
    rel_path = _rel_path(path)
    if _is_test_file(rel_path):
        return []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as exc:
        raise AssertionError(f"无法解析文件 {path}: {exc}") from exc
    return _check_tree(rel_path, tree)


def _find_violations() -> List[Violation]:
    violations: List[Violation] = []
    for dirname in SCAN_DIRS:
        for path in sorted((ROOT / dirname).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            violations.extend(_check_file(path))
    return violations


def test_no_new_inplace_mutation_after_entity_get() -> None:
    """新增代码不得在 get 之后就地修改组件（既有违规见 GRANDFATHERED）。"""
    new_violations = [
        violation
        for violation in _find_violations()
        if violation.key not in GRANDFATHERED
    ]
    assert (
        not new_violations
    ), "以下位置在 Entity.get 之后就地修改了组件；运行期请改为新建值再 Entity.replace：\n" + "\n".join(
        v.format() for v in new_violations
    )


def test_grandfathered_violations_are_all_fixed_or_listed() -> None:
    """修复后请把对应条目从 GRANDFATHERED 删除，保持这份清单是待办而非噪音。"""
    current: Set[Tuple[str, str]] = {v.key for v in _find_violations()}
    stale = sorted(GRANDFATHERED - current)
    assert (
        not stale
    ), "以下位置已不再就地修改组件，请从 GRANDFATHERED 删除：\n" + "\n".join(
        f"{path} :: {function}" for path, function in stale
    )


def test_checker_flags_assigned_component_mutation() -> None:
    source = """
def react(self, entity):
    comp = entity.get(HandComponent)
    comp.cards = []
"""
    violations = _check_source(source, "src/ai_rpg/systems/fake.py")
    assert [(v.function, v.line) for v in violations] == [("react", 4)]


def test_checker_flags_direct_chain_mutation() -> None:
    source = """
def react(self, entity):
    entity.get(EquippedGearComponent).items.append(item)
"""
    violations = _check_source(source, "src/ai_rpg/systems/fake.py")
    assert [(v.function, v.line) for v in violations] == [("react", 3)]


def test_checker_flags_list_mutation_via_alias() -> None:
    source = """
def react(self, entity):
    hand = entity.get(HandComponent)
    cards = hand.cards
    cards.pop(0)
"""
    violations = _check_source(source, "src/ai_rpg/systems/fake.py")
    assert [(v.function, v.line) for v in violations] == [("react", 5)]


def test_checker_flags_nested_component_mutation() -> None:
    source = """
def react(self, entity):
    stats = entity.get(CharacterStatsComponent)
    stats.stats.hp = 1
"""
    violations = _check_source(source, "src/ai_rpg/systems/fake.py")
    assert [(v.function, v.line) for v in violations] == [("react", 4)]


def test_checker_flags_provider_helper_mutation() -> None:
    source = """
def _pile_cards(entity, pile):
    return entity.get(HandComponent).cards

def react(self, entity):
    _pile_cards(entity, "hand").append(card)
    target = _pile_cards(entity, "hand")
    target.clear()
"""
    violations = _check_source(source, "src/ai_rpg/systems/fake.py")
    assert [(v.function, v.line) for v in violations] == [
        ("react", 6),
        ("react", 8),
    ]


def test_checker_allows_readonly_get_and_replace() -> None:
    source = """
def react(self, entity):
    comp = entity.get(HandComponent)
    count = len(comp.cards)
    entity.replace(HandComponent, comp.name, list(comp.cards))
    entity.get(PlayerComponent)
"""
    assert _check_source(source, "src/ai_rpg/systems/fake.py") == []


def test_checker_ignores_container_mutation() -> None:
    source = """
def build(processors, seen, db):
    processors.add(PrologueSystem(None))
    seen.add("name")
    db.add(document)
"""
    assert _check_source(source, "src/ai_rpg/systems/fake.py") == []


def test_checker_exempts_tests_directory() -> None:
    source = """
def make(entity):
    comp = entity.get(HandComponent)
    comp.cards = []
"""
    path = ROOT / "tests" / "unit" / "fake_test.py"
    assert _check_file(path) == []
    assert _check_source(source, "tests/unit/fake_test.py") != []
