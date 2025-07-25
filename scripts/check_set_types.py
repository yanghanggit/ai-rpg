#!/usr/bin/env python3
"""
检查 models 目录下所有 BaseModel 继承类是否包含 set 类型的属性
如果发现 set 类型，就报警
"""

import ast
import os
import sys
from pathlib import Path
from typing import List, Tuple, Set, Optional


class SetTypeChecker(ast.NodeVisitor):
    """AST 访问器，用于检查类定义中的 set 类型"""

    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.warnings: List[Tuple[str, str, int, str]] = (
            []
        )  # (filename, class_name, line_number, attribute_info)
        self.current_class: Optional[str] = None
        self.basemodel_classes: Set[str] = set()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """访问类定义"""
        # 检查是否继承自 BaseModel
        is_basemodel = False
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id == "BaseModel":
                is_basemodel = True
                break
            elif isinstance(base, ast.Attribute) and base.attr == "BaseModel":
                is_basemodel = True
                break

        if is_basemodel:
            self.basemodel_classes.add(node.name)
            self.current_class = node.name

            # 检查类属性的类型注解
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign) and stmt.annotation:
                    attr_name = self._get_target_name(stmt.target)
                    if attr_name and self._is_set_type(stmt.annotation):
                        type_str = self._annotation_to_string(stmt.annotation)
                        self.warnings.append(
                            (
                                self.filename,
                                node.name,
                                stmt.lineno,
                                f"属性 '{attr_name}' 的类型是 '{type_str}'",
                            )
                        )

        # 继续访问子节点
        self.generic_visit(node)
        self.current_class = None

    def _get_target_name(self, target: ast.expr) -> Optional[str]:
        """获取赋值目标的名称"""
        if isinstance(target, ast.Name):
            return target.id
        return None

    def _is_set_type(self, annotation: ast.expr) -> bool:
        """检查类型注解是否是 set 类型"""
        # 直接的 set 类型
        if isinstance(annotation, ast.Name) and annotation.id == "set":
            return True

        # Set 类型 (来自 typing)
        if isinstance(annotation, ast.Name) and annotation.id == "Set":
            return True

        # typing.Set
        if isinstance(annotation, ast.Attribute) and annotation.attr == "Set":
            return True

        # 泛型 Set[T] 或 set[T]
        if isinstance(annotation, ast.Subscript):
            if isinstance(annotation.value, ast.Name):
                if annotation.value.id in ("set", "Set"):
                    return True
            elif isinstance(annotation.value, ast.Attribute):
                if annotation.value.attr in ("set", "Set"):
                    return True

        return False

    def _annotation_to_string(self, annotation: ast.expr) -> str:
        """将类型注解转换为字符串"""
        try:
            return ast.unparse(annotation)
        except:
            return str(type(annotation).__name__)


def scan_python_files(models_dir: Path) -> List[Path]:
    """扫描 models 目录下的所有 Python 文件"""
    python_files = []
    for file_path in models_dir.rglob("*.py"):
        if file_path.name != "__init__.py":  # 跳过 __init__.py
            python_files.append(file_path)
    return python_files


def check_file_for_set_types(file_path: Path) -> List[Tuple[str, str, int, str]]:
    """检查单个文件中的 set 类型"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 解析 AST
        tree = ast.parse(content, filename=str(file_path))

        # 创建检查器并访问 AST
        checker = SetTypeChecker(str(file_path))
        checker.visit(tree)

        return checker.warnings

    except Exception as e:
        print(f"警告: 无法解析文件 {file_path}: {e}")
        return []


def main() -> None:
    """主函数"""
    # 确定 models 目录路径
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    models_dir = project_root / "src" / "multi_agents_game" / "models"

    if not models_dir.exists():
        print(f"错误: models 目录不存在: {models_dir}")
        sys.exit(1)

    print(f"开始扫描 models 目录: {models_dir}")
    print("=" * 60)

    # 扫描所有 Python 文件
    python_files = scan_python_files(models_dir)
    print(f"找到 {len(python_files)} 个 Python 文件")

    # 检查每个文件
    all_warnings = []
    basemodel_classes_found = 0

    for file_path in python_files:
        warnings = check_file_for_set_types(file_path)
        if warnings:
            all_warnings.extend(warnings)

        # 统计 BaseModel 类的数量
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            tree = ast.parse(content)
            checker = SetTypeChecker(str(file_path))
            checker.visit(tree)
            basemodel_classes_found += len(checker.basemodel_classes)
        except:
            pass

    print(f"总共检查了 {basemodel_classes_found} 个 BaseModel 继承类")
    print("=" * 60)

    # 报告结果
    if all_warnings:
        print("🚨 发现 set 类型警告:")
        print("=" * 60)

        for filename, class_name, line_number, attr_info in all_warnings:
            rel_path = Path(filename).relative_to(project_root)
            print(f"文件: {rel_path}")
            print(f"类名: {class_name}")
            print(f"行号: {line_number}")
            print(f"问题: {attr_info}")
            print("-" * 40)

        print(f"\n总共发现 {len(all_warnings)} 个 set 类型问题!")
        print("建议: 将 set 类型替换为 list 或其他支持序列化的类型")
        sys.exit(1)
    else:
        print("✅ 没有发现 set 类型问题!")
        print("所有 BaseModel 继承类都符合要求")
        sys.exit(0)


if __name__ == "__main__":
    main()
