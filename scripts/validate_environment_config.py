#!/usr/bin/env python3
"""
环境配置验证脚本
验证pyproject.toml, requirements.txt和environment.yml之间的一致性
"""

import tomllib
from typing import Any, Dict, List

import yaml  # type: ignore[import-untyped]


def load_environment_yml() -> Any:
    """加载environment.yml"""
    with open("environment.yml", "r") as f:
        return yaml.safe_load(f)


def load_pyproject_toml() -> Dict[str, Any]:
    """加载pyproject.toml"""
    with open("pyproject.toml", "rb") as f:
        return tomllib.load(f)


def load_requirements_txt() -> List[str]:
    """加载requirements.txt"""
    with open("requirements.txt", "r") as f:
        lines = f.readlines()

    # 过滤注释和空行
    requirements = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#"):
            requirements.append(line)

    return requirements


def extract_package_name(requirement: str) -> str:
    """从依赖字符串中提取包名"""
    # 处理 >= 、 == 、 < 等版本符号
    for op in [">=", "==", "<=", "~=", ">", "<", "!="]:
        if op in requirement:
            return requirement.split(op)[0].strip()
    return requirement.strip()


def main() -> None:
    print("🔍 验证环境配置一致性...")
    print("=" * 50)

    # 加载配置文件
    try:
        env_config = load_environment_yml()
        pyproject_config = load_pyproject_toml()
        requirements_list = load_requirements_txt()
    except Exception as e:
        print(f"❌ 加载配置文件失败: {e}")
        return

    # 提取pip依赖
    pip_deps_env = []
    for dep in env_config["dependencies"]:
        if isinstance(dep, dict) and "pip" in dep:
            pip_deps_env = dep["pip"]
            break

    # 提取包名集合
    pip_packages_env = {
        extract_package_name(pkg)
        for pkg in pip_deps_env
        if not pkg.startswith("ai-rpg")
    }

    pyproject_packages = {
        extract_package_name(pkg) for pkg in pyproject_config["project"]["dependencies"]
    }

    requirements_packages = {extract_package_name(req) for req in requirements_list}

    print(f"📊 包数量统计:")
    print(f"  environment.yml (pip): {len(pip_packages_env)}")
    print(f"  pyproject.toml: {len(pyproject_packages)}")
    print(f"  requirements.txt: {len(requirements_packages)}")
    print()

    # 检查一致性
    missing_in_pyproject = pip_packages_env - pyproject_packages
    missing_in_requirements = pip_packages_env - requirements_packages
    extra_in_pyproject = pyproject_packages - pip_packages_env
    extra_in_requirements = requirements_packages - pip_packages_env

    print("🔍 一致性检查结果:")

    if not missing_in_pyproject and not extra_in_pyproject:
        print("✅ pyproject.toml 与 environment.yml 一致")
    else:
        if missing_in_pyproject:
            print(f"⚠️  pyproject.toml 缺少包: {missing_in_pyproject}")
        if extra_in_pyproject:
            print(f"⚠️  pyproject.toml 多余包: {extra_in_pyproject}")

    if not missing_in_requirements and not extra_in_requirements:
        print("✅ requirements.txt 与 environment.yml 一致")
    else:
        if missing_in_requirements:
            print(f"⚠️  requirements.txt 缺少包: {missing_in_requirements}")
        if extra_in_requirements:
            print(f"⚠️  requirements.txt 多余包: {extra_in_requirements}")

    # 检查conda与pip的分离
    conda_packages = [dep for dep in env_config["dependencies"] if isinstance(dep, str)]

    print(f"\n📦 包分布:")
    print(f"  Conda包: {len(conda_packages)}")
    print(f"  Pip包: {len(pip_packages_env)}")
    print(f"  总计: {len(conda_packages) + len(pip_packages_env)}")

    print("\n✅ 验证完成!")


if __name__ == "__main__":
    main()
