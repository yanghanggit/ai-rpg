#!/usr/bin/env python3
"""
开发环境信息收集脚本
收集并输出当前开发环境的详细信息
"""

import os
import sys
import platform
import subprocess
import psutil
import socket
from pathlib import Path
from datetime import datetime
from typing import Tuple, List, Dict

try:
    from importlib.metadata import distributions
except ImportError:
    # Python < 3.8 fallback
    import pkg_resources  # type: ignore
from multi_agents_game.config.db_config import (
    POSTGRES_DATABASE_URL,
)


def run_command(command: str) -> Tuple[str, str, int]:
    """执行命令并返回结果"""
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", "命令执行超时", 1
    except Exception as e:
        return "", str(e), 1


def get_system_info() -> None:
    """获取系统信息"""
    print("\n" + "=" * 50)
    print("🖥️  系统信息")
    print("=" * 50)

    # 基本系统信息
    print(f"操作系统: {platform.system()} {platform.release()}")
    print(f"系统版本: {platform.version()}")
    print(f"CPU架构: {platform.machine()}")
    print(f"处理器: {platform.processor()}")
    print(
        f"CPU核心数: {psutil.cpu_count(logical=False)} 物理核心, {psutil.cpu_count(logical=True)} 逻辑核心"
    )

    # 内存信息
    memory = psutil.virtual_memory()
    print(f"内存总量: {memory.total / (1024**3):.1f} GB")
    print(f"内存可用: {memory.available / (1024**3):.1f} GB")
    print(f"内存使用率: {memory.percent}%")

    # 磁盘信息
    disk = psutil.disk_usage("/")
    print(f"磁盘总容量: {disk.total / (1024**3):.1f} GB")
    print(f"磁盘可用空间: {disk.free / (1024**3):.1f} GB")
    print(f"磁盘使用率: {(disk.used / disk.total) * 100:.1f}%")

    # 网络信息
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
        print(f"主机名: {hostname}")
        print(f"本地IP: {local_ip}")
    except Exception:
        print(f"主机名: {hostname}")
        print("本地IP: 无法获取")


def get_python_environment() -> None:
    """获取Python环境信息"""
    print("\n" + "=" * 50)
    print("🐍 Python环境")
    print("=" * 50)

    print(f"Python版本: {sys.version}")
    print(f"Python可执行文件路径: {sys.executable}")
    print(f"Python路径: {sys.path[0]}")

    # 检查虚拟环境
    if hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    ):
        print("虚拟环境: 是 (venv/virtualenv)")
        print(f"虚拟环境路径: {sys.prefix}")
    elif os.environ.get("CONDA_DEFAULT_ENV"):
        print(f"虚拟环境: 是 (conda: {os.environ.get('CONDA_DEFAULT_ENV')})")
        print(f"Conda环境路径: {os.environ.get('CONDA_PREFIX', '未知')}")
    else:
        print("虚拟环境: 否 (使用系统Python)")

    # pip信息
    pip_stdout, pip_stderr, pip_code = run_command("pip --version")
    if pip_code == 0:
        print(f"pip版本: {pip_stdout}")
    else:
        print(f"pip状态: 获取失败 - {pip_stderr}")

    # 已安装包数量
    try:
        try:
            # 使用现代的 importlib.metadata
            installed_packages = list(distributions())
            print(f"已安装包数量: {len(installed_packages)}个")
        except NameError:
            # 回退到 pkg_resources
            installed_packages = list(pkg_resources.working_set)
            print(f"已安装包数量: {len(installed_packages)}个")
    except Exception as e:
        print(f"已安装包数量: 获取失败 - {e}")


def get_project_config() -> None:
    """获取项目配置信息"""
    print("\n" + "=" * 50)
    print("📁 项目配置")
    print("=" * 50)

    project_root = Path.cwd()
    print(f"当前工作目录: {project_root}")

    # Git信息
    git_branch, _, git_code = run_command("git branch --show-current")
    if git_code == 0:
        print(f"Git分支: {git_branch}")
    else:
        print("Git分支: 获取失败或不是Git仓库")

    git_remote, _, _ = run_command("git remote -v")
    if git_remote:
        print("Git远程仓库:")
        for line in git_remote.split("\n"):
            if line.strip():
                print(f"  {line}")

    # 检查配置文件
    config_files: Dict[str, str] = {
        "requirements.txt": "项目依赖",
        "requirements-dev.txt": "开发依赖",
        "pyproject.toml": "Python项目配置",
        "environment.yml": "Conda环境配置",
        "Makefile": "构建配置",
        "mypy.ini": "MyPy类型检查配置",
        "server_settings.json": "服务器配置",
        ".gitignore": "Git忽略规则",
        "README.md": "项目说明文档",
    }

    print("\n配置文件检查:")
    for file_name, description in config_files.items():
        file_path = project_root / file_name
        if file_path.exists():
            if file_name.endswith(".txt"):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    dependency_count = len(
                        [
                            line
                            for line in lines
                            if line.strip() and not line.strip().startswith("#")
                        ]
                    )
                    print(
                        f"  ✅ {file_name}: 存在 ({description}, {dependency_count}个依赖)"
                    )
                except Exception:
                    print(f"  ✅ {file_name}: 存在 ({description})")
            else:
                file_size = file_path.stat().st_size
                print(f"  ✅ {file_name}: 存在 ({description}, {file_size} bytes)")
        else:
            print(f"  ❌ {file_name}: 不存在 ({description})")


def get_development_tools() -> None:
    """获取开发工具信息"""
    print("\n" + "=" * 50)
    print("🔧 开发工具")
    print("=" * 50)

    tools: Dict[str, str] = {
        "git --version": "Git版本控制",
        "node --version": "Node.js",
        "npm --version": "NPM包管理器",
        "docker --version": "Docker容器",
        "docker-compose --version": "Docker Compose",
        "redis-cli --version": "Redis CLI",
        "psql --version": "PostgreSQL客户端",
        "conda --version": "Conda包管理器",
    }

    for command, description in tools.items():
        stdout, stderr, code = run_command(command)
        if code == 0:
            print(f"  ✅ {description}: {stdout}")
        else:
            print(f"  ❌ {description}: 未安装或不可用")


def get_network_and_services() -> None:
    """获取网络和服务信息"""
    print("\n" + "=" * 50)
    print("🌐 网络和服务")
    print("=" * 50)

    # 检查常用端口
    common_ports: Dict[int, str] = {
        3000: "React/Next.js开发服务器",
        8000: "Django/FastAPI开发服务器",
        8080: "HTTP备用端口",
        5432: "PostgreSQL数据库",
        6379: "Redis数据库",
        27017: "MongoDB数据库",
        3306: "MySQL数据库",
    }

    print("端口占用情况:")
    for port, description in common_ports.items():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(("localhost", port))
        sock.close()

        if result == 0:
            print(f"  🟢 端口 {port}: 已占用 ({description})")
        else:
            print(f"  ⚪ 端口 {port}: 可用 ({description})")

    # 测试数据库连接
    print("\n数据库连接测试:")

    # Redis连接测试
    try:
        import redis

        r = redis.Redis(host="localhost", port=6379, db=0, socket_timeout=2)
        r.ping()
        print("  ✅ Redis: 连接成功")
    except ImportError:
        print("  ⚠️  Redis: redis库未安装")
    except Exception as e:
        print(f"  ❌ Redis: 连接失败 - {e}")

    # PostgreSQL连接测试 - 使用项目配置
    try:
        import psycopg2

        # 尝试使用项目配置的数据库连接
        try:
            conn = psycopg2.connect(POSTGRES_DATABASE_URL, connect_timeout=2)
            conn.close()
            print("  ✅ PostgreSQL (项目数据库): 连接成功")
            print(
                f"    数据库URL: {POSTGRES_DATABASE_URL.replace(':123456@', ':***@')}"
            )  # 隐藏密码
        except Exception as project_db_error:
            print(f"  ❌ PostgreSQL (项目数据库): 连接失败 - {project_db_error}")

            # 如果项目数据库连接失败，尝试连接默认postgres数据库
            try:
                conn = psycopg2.connect(
                    host="localhost",
                    port=5432,
                    database="postgres",
                    user="postgres",
                    connect_timeout=2,
                )
                conn.close()
                print("  ✅ PostgreSQL (默认数据库): 连接成功")
            except Exception as default_db_error:
                print(f"  ❌ PostgreSQL (默认数据库): 连接失败 - {default_db_error}")

    except ImportError:
        print("  ⚠️  PostgreSQL: psycopg2库未安装")
    except Exception as e:
        print(f"  ❌ PostgreSQL: 连接测试失败 - {e}")


def get_dependency_analysis() -> None:
    """分析项目依赖"""
    print("\n" + "=" * 50)
    print("📦 依赖分析")
    print("=" * 50)

    project_root = Path.cwd()

    # 分析requirements.txt
    req_file = project_root / "requirements.txt"
    if req_file.exists():
        try:
            with open(req_file, "r", encoding="utf-8") as f:
                requirements = f.readlines()

            dependencies: List[str] = []
            for line in requirements:
                line = line.strip()
                if line and not line.startswith("#"):
                    dependencies.append(line)

            print(f"requirements.txt依赖数量: {len(dependencies)}")

            # 检查核心依赖
            core_deps: List[str] = [
                "fastapi",
                "aiohttp",
                "langchain",
                "redis",
                "psycopg2",
            ]
            print("核心依赖检查:")
            for dep in core_deps:
                found = any(dep in req_line.lower() for req_line in dependencies)
                if found:
                    version = next(
                        (
                            req_line
                            for req_line in dependencies
                            if dep in req_line.lower()
                        ),
                        "",
                    )
                    print(f"  ✅ {dep}: {version}")
                else:
                    print(f"  ❌ {dep}: 未找到")

        except Exception as e:
            print(f"requirements.txt分析失败: {e}")

    # 检查已安装包与requirements的匹配情况
    print("\n已安装包验证:")
    try:
        try:
            # 使用现代的 importlib.metadata
            installed = {
                dist.metadata["name"].lower(): dist.version for dist in distributions()
            }
        except NameError:
            # 回退到 pkg_resources
            installed = {
                pkg.project_name.lower(): pkg.version
                for pkg in pkg_resources.working_set
            }

        if req_file.exists():
            with open(req_file, "r", encoding="utf-8") as f:
                requirements = f.readlines()

            missing_packages: List[str] = []
            for line in requirements:
                line = line.strip()
                if line and not line.startswith("#"):
                    if "==" in line:
                        pkg_name = line.split("==")[0].lower()
                        required_version = line.split("==")[1]
                        if pkg_name in installed:
                            if installed[pkg_name] != required_version:
                                print(
                                    f"  ⚠️  {pkg_name}: 版本不匹配 (需要{required_version}, 已安装{installed[pkg_name]})"
                                )
                        else:
                            missing_packages.append(pkg_name)

            if missing_packages:
                print(f"  ❌ 缺失包: {', '.join(missing_packages)}")
            else:
                print("  ✅ 所有依赖包都已正确安装")

    except Exception as e:
        print(f"依赖验证失败: {e}")


def get_environment_variables() -> None:
    """获取重要的环境变量"""
    print("\n" + "=" * 50)
    print("🔧 环境变量")
    print("=" * 50)

    important_env_vars: List[str] = [
        "PATH",
        "PYTHONPATH",
        "CONDA_DEFAULT_ENV",
        "CONDA_PREFIX",
        "VIRTUAL_ENV",
        "HOME",
        "USER",
        "SHELL",
        "DATABASE_URL",
        "REDIS_URL",
        "OPENAI_API_KEY",
    ]

    for var in important_env_vars:
        value = os.environ.get(var)
        if value:
            # 隐藏敏感信息
            if (
                "key" in var.lower()
                or "password" in var.lower()
                or "secret" in var.lower()
            ):
                masked_value = (
                    value[:4] + "*" * (len(value) - 8) + value[-4:]
                    if len(value) > 8
                    else "*" * len(value)
                )
                print(f"  {var}: {masked_value}")
            elif var == "PATH":
                # PATH变量太长，只显示前几个路径
                paths = value.split(os.pathsep)[:5]
                print(
                    f"  {var}: {os.pathsep.join(paths)}... ({len(value.split(os.pathsep))}个路径)"
                )
            else:
                print(f"  {var}: {value}")
        else:
            print(f"  {var}: 未设置")


def main() -> None:
    """主函数"""
    print("🚀 开发环境信息收集工具")
    print("=" * 50)
    print(f"收集时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"脚本路径: {__file__}")

    try:
        get_system_info()
        get_python_environment()
        get_project_config()
        get_development_tools()
        get_network_and_services()
        get_dependency_analysis()
        get_environment_variables()

        print("\n" + "=" * 50)
        print("✅ 环境信息收集完成")
        print("=" * 50)

    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断了信息收集过程")
    except Exception as e:
        print(f"\n\n❌ 收集过程中发生错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
