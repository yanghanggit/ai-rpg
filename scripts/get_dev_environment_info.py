#!/usr/bin/env python3
"""
开发环境信息收集脚本
收集并输出当前开发环境的详细信息
"""

import os
import sys

# 将 src 目录添加到模块搜索路径
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

import platform
import socket
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import psutil

try:
    from importlib.metadata import distributions
except ImportError:
    # Python < 3.8 fallback
    import pkg_resources
from ai_rpg.pgsql import (
    postgresql_config,
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
            pkg_resources_packages = [dist for dist in pkg_resources.working_set]
            print(f"已安装包数量: {len(pkg_resources_packages)}个")
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
        "pyproject.toml": "Python项目配置",
        "Makefile": "构建配置",
        "mypy.ini": "MyPy类型检查配置",
        ".gitignore": "Git忽略规则",
        "README.md": "项目说明文档",
    }

    print("\n配置文件检查:")
    for file_name, description in config_files.items():
        file_path = project_root / file_name
        if file_path.exists():
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
        "neo4j version": "Neo4j数据库",
        "cypher-shell --version": "Neo4j Cypher Shell",
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
        7687: "Neo4j Bolt协议",
        7474: "Neo4j HTTP Web界面",
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
            conn = psycopg2.connect(
                postgresql_config.connection_string, connect_timeout=2
            )
            conn.close()
            print("  ✅ PostgreSQL (项目数据库): 连接成功")
            print(
                f"    数据库URL: {postgresql_config.connection_string.replace(':123456@', ':***@')}"
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


def get_neo4j_environment() -> None:
    """获取Neo4j环境信息"""
    print("\n" + "=" * 50)
    print("🔗 Neo4j图数据库环境")
    print("=" * 50)

    # 检查Neo4j Python驱动安装状态
    try:
        import neo4j
        from neo4j import GraphDatabase

        print(f"  ✅ Neo4j Python驱动: 已安装 (版本 {neo4j.__version__})")

        # 检查关键组件
        try:
            from neo4j.exceptions import ServiceUnavailable, AuthError

            print("  ✅ Neo4j异常类: 可用")
        except ImportError as e:
            print(f"  ⚠️  Neo4j异常类: 导入失败 - {e}")

        # 检查Neo4j服务状态
        print("\n  Neo4j服务检查:")

        # 检查端口占用 (Neo4j默认端口)
        neo4j_ports = {
            7687: "Bolt协议端口",
            7474: "HTTP Web界面端口",
            7473: "HTTPS端口",
        }

        for port, description in neo4j_ports.items():
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(("localhost", port))
            sock.close()

            if result == 0:
                print(f"    🟢 端口 {port}: 已占用 ({description})")
            else:
                print(f"    ⚪ 端口 {port}: 可用 ({description})")

        # Neo4j连接测试
        print("\n  Neo4j连接测试:")
        try:
            # 尝试连接Neo4j数据库
            driver = GraphDatabase.driver(
                "bolt://localhost:7687",
                auth=("neo4j", "password123"),
                connection_timeout=3,
            )

            # 测试连接
            with driver.session() as session:
                test_result = session.run("RETURN 1 as test")
                test_record = test_result.single()
                if test_record:
                    test_value = test_record["test"]
                    if test_value == 1:
                        print("    ✅ Neo4j数据库: 连接成功")

                        # 获取服务器信息
                        try:
                            components_result = session.run(
                                "CALL dbms.components() YIELD name, versions, edition"
                            )
                            for record in components_result:
                                print(
                                    f"    📊 {record['name']}: {record['versions'][0]} ({record['edition']})"
                                )
                        except Exception as info_error:
                            print(f"    ⚠️  服务器信息获取失败: {info_error}")

                        # 检查数据库状态
                        try:
                            databases_result = session.run("SHOW DATABASES")
                            databases = [record["name"] for record in databases_result]
                            print(f"    🗄️  可用数据库: {', '.join(databases)}")
                        except Exception:
                            # 某些版本可能不支持SHOW DATABASES
                            print("    🗄️  数据库信息: 无法获取 (可能权限不足)")
                    else:
                        print("    ❌ Neo4j连接测试失败")
                else:
                    print("    ❌ Neo4j连接测试失败：无返回结果")

            driver.close()

        except AuthError:
            print("    ❌ Neo4j认证失败 (用户名/密码错误)")
            print("    💡 建议检查密码或访问 http://localhost:7474 重新设置")
        except ServiceUnavailable:
            print("    ❌ Neo4j服务不可用 (服务未启动)")
            print("    💡 启动建议: brew services start neo4j")
        except Exception as e:
            print(f"    ❌ Neo4j连接失败: {e}")

        # 检查Neo4j命令行工具
        print("\n  Neo4j命令行工具:")
        neo4j_tools = {
            "neo4j version": "Neo4j服务器",
            "cypher-shell --version": "Cypher Shell客户端",
        }

        for command, description in neo4j_tools.items():
            stdout, stderr, code = run_command(command)
            if code == 0:
                print(f"    ✅ {description}: {stdout}")
            else:
                print(f"    ❌ {description}: 未安装或不可用")

        # 检查Neo4j安装方式
        print("\n  Neo4j安装检查:")

        # 检查Homebrew安装
        homebrew_neo4j, _, homebrew_code = run_command("brew list neo4j")
        if homebrew_code == 0:
            print("    ✅ Neo4j通过Homebrew安装")
            # 获取安装路径
            neo4j_path, _, _ = run_command("brew --prefix neo4j")
            if neo4j_path:
                print(f"    📁 安装路径: {neo4j_path}")
        else:
            print("    ⚪ Neo4j未通过Homebrew安装")

        # 检查Docker安装
        docker_neo4j, _, docker_code = run_command(
            "docker ps --filter name=neo4j --format '{{.Names}}'"
        )
        if docker_code == 0 and docker_neo4j.strip():
            print(f"    ✅ Neo4j Docker容器运行中: {docker_neo4j.strip()}")
        else:
            print("    ⚪ 无Neo4j Docker容器运行")

        # 检查配置文件
        print("\n  Neo4j配置文件:")
        potential_config_paths = [
            "/opt/homebrew/etc/neo4j/neo4j.conf",
            "/usr/local/etc/neo4j/neo4j.conf",
            "~/.neo4j/neo4j.conf",
            "/etc/neo4j/neo4j.conf",
        ]

        config_found = False
        for config_path in potential_config_paths:
            expanded_path = os.path.expanduser(config_path)
            if os.path.exists(expanded_path):
                print(f"    ✅ 配置文件: {config_path}")
                config_found = True
                break

        if not config_found:
            print("    ⚪ 未找到标准位置的配置文件")

        # Java环境检查 (Neo4j需要Java)
        print("\n  Java环境检查 (Neo4j依赖):")
        java_version, _, java_code = run_command("java -version")
        if java_code == 0:
            # 解析Java版本
            java_info = java_version.split("\n")[0] if java_version else "未知版本"
            print(f"    ✅ Java: {java_info}")

            # 检查JAVA_HOME
            java_home = os.environ.get("JAVA_HOME")
            if java_home:
                print(f"    ✅ JAVA_HOME: {java_home}")
            else:
                print("    ⚠️  JAVA_HOME: 未设置")
        else:
            print("    ❌ Java: 未安装 (Neo4j需要Java运行)")

    except ImportError:
        print("  ❌ Neo4j Python驱动: 未安装")
        print("  💡 安装建议:")
        print("    conda环境: conda install neo4j-python-driver")
        print("    或者: pip install neo4j")

        # 即使驱动未安装，也检查服务状态
        print("\n  Neo4j服务状态检查 (无驱动):")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        bolt_result = sock.connect_ex(("localhost", 7687))
        sock.close()

        sock2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock2.settimeout(1)
        http_result = sock2.connect_ex(("localhost", 7474))
        sock2.close()

        if bolt_result == 0 or http_result == 0:
            print("    🟢 Neo4j服务似乎正在运行")
            print("    💡 安装Python驱动后可进行完整测试")
        else:
            print("    ⚪ Neo4j服务未检测到")

    except Exception as e:
        print(f"  ❌ Neo4j环境检查失败: {e}")


def get_chromadb_environment() -> None:
    """获取ChromaDB环境信息"""
    print("\n" + "=" * 50)
    print("🗄️  ChromaDB向量数据库环境")
    print("=" * 50)

    # 检查ChromaDB安装状态
    try:
        import chromadb

        print(f"  ✅ ChromaDB: 已安装 (版本 {chromadb.__version__})")

        # 检查ChromaDB的主要组件
        try:
            from chromadb.config import Settings  # noqa: F401 # 用于检测模块可用性

            print("  ✅ ChromaDB Settings: 可用")
        except ImportError as e:
            print(f"  ⚠️  ChromaDB Settings: 导入失败 - {e}")

        try:
            from chromadb.api import ClientAPI  # noqa: F401 # 用于检测模块可用性

            print("  ✅ ChromaDB ClientAPI: 可用")
        except ImportError as e:
            print(f"  ⚠️  ChromaDB ClientAPI: 导入失败 - {e}")

        # 检查embedding函数
        try:
            from chromadb.utils import embedding_functions

            print("  ✅ ChromaDB Embedding Functions: 可用")

            # 列出可用的embedding函数类型
            available_embeddings = []
            if hasattr(embedding_functions, "DefaultEmbeddingFunction"):
                available_embeddings.append("DefaultEmbeddingFunction")
            if hasattr(embedding_functions, "SentenceTransformerEmbeddingFunction"):
                available_embeddings.append("SentenceTransformerEmbeddingFunction")
            if hasattr(embedding_functions, "OpenAIEmbeddingFunction"):
                available_embeddings.append("OpenAIEmbeddingFunction")
            if hasattr(embedding_functions, "HuggingFaceEmbeddingFunction"):
                available_embeddings.append("HuggingFaceEmbeddingFunction")

            if available_embeddings:
                print(f"    可用的Embedding函数: {', '.join(available_embeddings)}")

        except ImportError as e:
            print(f"  ⚠️  ChromaDB Embedding Functions: 导入失败 - {e}")

        # 检查ChromaDB依赖
        chroma_dependencies = [
            "sentence-transformers",
            "onnxruntime",
            "tokenizers",
            "huggingface-hub",
            "transformers",
        ]

        print("\n  ChromaDB相关依赖检查:")
        try:
            try:
                installed = {
                    dist.metadata["name"].lower(): dist.version
                    for dist in distributions()
                }
            except NameError:
                installed = {
                    pkg.project_name.lower(): pkg.version
                    for pkg in pkg_resources.working_set
                }

            for dep in chroma_dependencies:
                # 检查不同的包名格式
                found_version = None
                for pkg_name, version in installed.items():
                    if (
                        dep == pkg_name
                        or dep.replace("-", "_") == pkg_name
                        or dep.replace("_", "-") == pkg_name
                    ):
                        found_version = version
                        break

                if found_version:
                    print(f"    ✅ {dep}: {found_version}")
                else:
                    print(f"    ❌ {dep}: 未安装")

        except Exception as e:
            print(f"    ⚠️  依赖检查失败: {e}")

        # ChromaDB连接测试
        print("\n  ChromaDB连接测试:")
        try:
            # 创建临时客户端进行连接测试
            client = chromadb.Client()
            print("    ✅ ChromaDB Client: 创建成功")

            # 简单检查集合列表
            try:
                collections = client.list_collections()
                print(f"    ✅ 现有集合数量: {len(collections)}")
                if collections:
                    collection_names = [col.name for col in collections]
                    print(
                        f"    📚 集合列表: {', '.join(collection_names[:5])}{'...' if len(collection_names) > 5 else ''}"
                    )
            except Exception as e:
                print(f"    ⚠️  集合操作失败: {e}")

        except Exception as e:
            print(f"    ❌ ChromaDB Client创建失败: {e}")

        # 检查ChromaDB持久化设置
        print("\n  ChromaDB配置信息:")
        try:
            # 检查默认设置
            settings = chromadb.get_settings()
            if hasattr(settings, "persist_directory"):
                print(f"    📁 持久化目录: {settings.persist_directory}")
            if hasattr(settings, "chroma_db_impl"):
                print(f"    🔧 数据库实现: {settings.chroma_db_impl}")
            if hasattr(settings, "chroma_api_impl"):
                print(f"    🔌 API实现: {settings.chroma_api_impl}")
        except Exception as e:
            print(f"    ⚠️  配置获取失败: {e}")

        # 检查可用的embedding模型
        print("\n  Embedding模型检查:")
        try:
            from sentence_transformers import (  # noqa: F401 # 用于检测模块可用性
                SentenceTransformer,
            )

            print("    🤖 Sentence Transformers: 可用")

            # 检查是否可以创建默认embedding函数
            try:
                from chromadb.utils.embedding_functions import (  # noqa: F401 # 用于检测模块可用性
                    SentenceTransformerEmbeddingFunction,
                )

                print("    ✅ SentenceTransformerEmbeddingFunction: 可用")
            except ImportError:
                print("    ⚠️  SentenceTransformerEmbeddingFunction: 不可用")

        except ImportError:
            print("    ⚠️  Sentence Transformers未安装")
        except Exception as e:
            print(f"    ⚠️  模型检查失败: {e}")

    except ImportError:
        print("  ❌ ChromaDB: 未安装")
        print("  💡 安装建议:")
        print("    conda环境: pip install chromadb")
        print("    或者: conda install -c conda-forge chromadb")

        # 检查相关包是否缺失
        missing_deps = []
        related_packages = ["sentence-transformers", "onnxruntime", "tokenizers"]

        try:
            try:
                installed = {
                    dist.metadata["name"].lower(): dist.version
                    for dist in distributions()
                }
            except NameError:
                installed = {
                    pkg.project_name.lower(): pkg.version
                    for pkg in pkg_resources.working_set
                }

            for pkg in related_packages:
                if not any(
                    pkg == name or pkg.replace("-", "_") == name
                    for name in installed.keys()
                ):
                    missing_deps.append(pkg)

            if missing_deps:
                print(f"  ⚠️  相关缺失依赖: {', '.join(missing_deps)}")

        except Exception:
            pass

    except Exception as e:
        print(f"  ❌ ChromaDB环境检查失败: {e}")


def get_dependency_analysis() -> None:
    """分析项目依赖"""
    print("\n" + "=" * 50)
    print("📦 依赖分析")
    print("=" * 50)

    # 检查核心依赖的安装状态
    print("核心依赖检查:")
    try:
        # 获取已安装包列表
        try:
            installed = {
                dist.metadata["name"].lower(): dist.version for dist in distributions()
            }
        except NameError:
            installed = {
                pkg.project_name.lower(): pkg.version
                for pkg in pkg_resources.working_set
            }

        core_deps: List[str] = [
            "fastapi",
            "aiohttp",
            "langchain",
            "redis",
            "psycopg2",
            "pydantic",
            "numpy",
            "pandas",
            "chromadb",
        ]

        for dep in core_deps:
            # 检查是否已安装
            installed_version = None
            for pkg_name, version in installed.items():
                if dep == pkg_name or dep in pkg_name:
                    installed_version = version
                    break

            if installed_version:
                print(f"  ✅ {dep}: {installed_version}")
            else:
                print(f"  ❌ {dep}: 未安装")

    except Exception as e:
        print(f"核心依赖检查失败: {e}")


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
        get_neo4j_environment()
        get_chromadb_environment()
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
