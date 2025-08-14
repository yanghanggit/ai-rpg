#!/usr/bin/env python3
"""
检查和清理项目中未使用的导入的脚本

使用方法：
    python scripts/check_unused_imports.py --check          # 检查 src/ 和 scripts/，不修改
    python scripts/check_unused_imports.py --fix            # 自动修复 src/ 和 scripts/
    python scripts/check_unused_imports.py --check-file <filepath>  # 检查单个文件
    python scripts/check_unused_imports.py --check --ignore-unused-imports  # 检查但忽略F401错误

    python scripts/check_unused_imports.py --check --file src/      # 只检查 src/
    python scripts/check_unused_imports.py --check --file scripts/  # 只检查 scripts/
"""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List, Union


def run_ruff_check(
    target_paths: Union[str, List[str]],
    fix: bool = False,
    ignore_unused_imports: bool = False,
) -> int:
    """运行ruff检查未使用的导入"""
    cmd = ["ruff", "check"]

    if ignore_unused_imports:
        # 忽略未使用的导入错误和star import错误
        cmd.extend(["--ignore", "F401,F403"])
    else:
        # 只检查未使用的导入
        cmd.extend(["--select", "F401"])

    if fix:
        cmd.append("--fix")

    # 支持单个路径（字符串）或多个路径（列表）
    if isinstance(target_paths, str):
        cmd.append(target_paths)
    else:
        cmd.extend(target_paths)

    print(f"运行命令: {' '.join(cmd)}")
    print("-" * 50)

    try:
        result = subprocess.run(cmd, capture_output=False, text=True)
        return result.returncode
    except FileNotFoundError:
        print("错误: 找不到ruff命令。请确保已安装ruff:")
        print("  conda install -c conda-forge ruff")
        print("  或者: pip install ruff")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="检查和清理未使用的导入")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--check", action="store_true", help="检查未使用的导入（不修改文件）"
    )
    group.add_argument("--fix", action="store_true", help="自动修复未使用的导入")

    parser.add_argument("--file", help="指定要检查的单个文件路径")
    parser.add_argument(
        "--ignore-unused-imports",
        action="store_true",
        help="忽略未使用的导入错误（F401）",
    )

    args = parser.parse_args()

    # 确保在项目根目录运行
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    # 切换到项目根目录
    import os

    os.chdir(project_root)

    # 确定检查目标
    if args.file:
        target = args.file
        target_display = target
    else:
        target = ["src/", "scripts/"]
        target_display = "src/ 和 scripts/"

    if args.check:
        print(f"🔍 检查 {target_display} 中的未使用导入...")
        return_code = run_ruff_check(
            target, fix=False, ignore_unused_imports=args.ignore_unused_imports
        )
        if return_code == 0:
            if args.ignore_unused_imports:
                print("✅ 代码检查完成（已忽略未使用的导入）！")
            else:
                print("✅ 没有发现未使用的导入！")
        else:
            print("❌ 发现未使用的导入，请查看上面的输出。")
            print("💡 提示：使用 --fix 参数可以自动修复这些问题。")

    elif args.fix:
        print(f"🔧 修复 {target_display} 中的未使用导入...")
        return_code = run_ruff_check(
            target, fix=True, ignore_unused_imports=args.ignore_unused_imports
        )
        if return_code == 0:
            if args.ignore_unused_imports:
                print("✅ 代码检查和修复完成（已忽略未使用的导入）！")
            else:
                print("✅ 所有未使用的导入已清理！")
        else:
            print("❌ 修复过程中遇到一些问题，请查看上面的输出。")

    return return_code


if __name__ == "__main__":
    sys.exit(main())
