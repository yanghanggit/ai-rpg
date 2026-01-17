#!/usr/bin/env python3
"""
ChromaDB环境测试
测试ChromaDB的基本功能和集成状态
"""

import pytest
import time
from typing import List as ListType, cast
from collections.abc import Sequence


def check_huggingface_connectivity(timeout: float = 5.0) -> bool:
    """
    检测HuggingFace网络连通性

    Args:
        timeout: 超时时间（秒）

    Returns:
        bool: 连接正常返回True，否则返回False
    """
    try:
        import requests

        print(f"🔍 正在检测HuggingFace网络连通性（超时: {timeout}秒）...")
        response = requests.head(
            "https://huggingface.co", timeout=timeout, allow_redirects=True
        )

        if response.status_code < 500:  # 任何非服务器错误都算通
            print(f"✅ HuggingFace网络连接正常 (状态码: {response.status_code})")
            return True
        else:
            print(f"⚠️  HuggingFace服务器响应异常 (状态码: {response.status_code})")
            return False

    except requests.Timeout:
        print(f"⚠️  HuggingFace连接超时（>{timeout}秒）")
        return False
    except requests.ConnectionError as e:
        print(f"⚠️  HuggingFace连接失败: {type(e).__name__}")
        return False
    except Exception as e:
        print(f"⚠️  网络检测异常: {type(e).__name__}: {e}")
        return False


class TestChromaDBEnvironment:
    """ChromaDB环境测试类"""

    def test_chromadb_import(self) -> None:
        """测试ChromaDB导入"""
        try:
            import chromadb

            assert chromadb.__version__ is not None
            print(f"✅ ChromaDB版本: {chromadb.__version__}")
        except ImportError:
            pytest.fail("ChromaDB未安装")

    def test_chromadb_components(self) -> None:
        """测试ChromaDB主要组件"""
        try:
            from chromadb.config import Settings

            assert Settings is not None
        except ImportError:
            pytest.fail("ChromaDB Settings导入失败")

        try:
            from chromadb.api import ClientAPI

            assert ClientAPI is not None
        except ImportError:
            pytest.fail("ChromaDB ClientAPI导入失败")

        try:
            from chromadb.utils import embedding_functions

            assert embedding_functions is not None
        except ImportError:
            pytest.fail("ChromaDB Embedding Functions导入失败")

    def test_embedding_functions_availability(self) -> None:
        """测试embedding函数可用性"""
        from chromadb.utils import embedding_functions

        # 检查各种embedding函数是否可用
        available_functions = []

        if hasattr(embedding_functions, "DefaultEmbeddingFunction"):
            available_functions.append("DefaultEmbeddingFunction")
        if hasattr(embedding_functions, "SentenceTransformerEmbeddingFunction"):
            available_functions.append("SentenceTransformerEmbeddingFunction")
        if hasattr(embedding_functions, "OpenAIEmbeddingFunction"):
            available_functions.append("OpenAIEmbeddingFunction")
        if hasattr(embedding_functions, "HuggingFaceEmbeddingFunction"):
            available_functions.append("HuggingFaceEmbeddingFunction")

        assert len(available_functions) > 0, "没有找到可用的embedding函数"
        print(f"✅ 可用的Embedding函数: {', '.join(available_functions)}")

    def test_chromadb_dependencies(self) -> None:
        """测试ChromaDB相关依赖"""
        required_deps = [
            "sentence-transformers",
            "onnxruntime",
            "tokenizers",
            "huggingface-hub",
            "transformers",
        ]

        missing_deps = []
        for dep in required_deps:
            try:
                __import__(dep.replace("-", "_"))
            except ImportError:
                missing_deps.append(dep)

        if missing_deps:
            pytest.fail(f"缺失ChromaDB依赖: {', '.join(missing_deps)}")

    def test_chromadb_client_creation(self) -> None:
        """测试ChromaDB客户端创建"""
        import chromadb

        try:
            client = chromadb.Client()
            assert client is not None
            print("✅ ChromaDB Client创建成功")
        except Exception as e:
            pytest.fail(f"ChromaDB Client创建失败: {e}")

    def test_chromadb_collection_operations(self) -> None:
        """测试ChromaDB集合操作"""
        import chromadb

        client = chromadb.Client()
        test_collection_name = "pytest_test_collection"

        # 清理可能存在的测试集合
        try:
            client.delete_collection(test_collection_name)
        except Exception:
            pass

        try:
            # 创建测试集合
            collection = client.create_collection(test_collection_name)
            assert collection is not None
            print("✅ 集合创建测试成功")

            # 测试向量添加
            embeddings_data: ListType[ListType[float]] = [
                [1.0, 2.0, 3.0],
                [4.0, 5.0, 6.0],
            ]
            collection.add(
                embeddings=cast("list[Sequence[float]]", embeddings_data),
                documents=["测试文档1", "测试文档2"],
                ids=["test1", "test2"],
            )
            print("✅ 向量添加测试成功")

            # 测试向量查询
            query_embeddings_data: ListType[ListType[float]] = [[1.0, 2.0, 3.0]]
            results = collection.query(
                query_embeddings=cast("list[Sequence[float]]", query_embeddings_data),
                n_results=1,
            )

            assert results is not None
            assert "documents" in results
            assert results["documents"] is not None
            assert len(results["documents"]) > 0
            assert len(results["documents"][0]) > 0
            print("✅ 向量查询测试成功")

        finally:
            # 清理测试集合
            try:
                client.delete_collection(test_collection_name)
                print("✅ 测试清理完成")
            except Exception:
                pass

    def test_chromadb_settings(self) -> None:
        """测试ChromaDB配置设置"""
        import chromadb

        try:
            settings = chromadb.get_settings()
            assert settings is not None

            # 检查基本配置属性
            if hasattr(settings, "persist_directory"):
                print(f"✅ 持久化目录: {settings.persist_directory}")
            if hasattr(settings, "chroma_api_impl"):
                print(f"✅ API实现: {settings.chroma_api_impl}")

        except Exception as e:
            pytest.fail(f"ChromaDB设置获取失败: {e}")

    def test_sentence_transformers_availability(self) -> None:
        """测试Sentence Transformers可用性"""
        try:
            from sentence_transformers import SentenceTransformer

            assert SentenceTransformer is not None
            print("✅ Sentence Transformers可用")
        except ImportError:
            pytest.skip("Sentence Transformers未安装，跳过测试")

    def test_chromadb_with_sentence_transformers(self) -> None:
        """测试ChromaDB与Sentence Transformers集成"""
        print("\n" + "=" * 60)
        print("🔍 [TEST START] test_chromadb_with_sentence_transformers")
        start_test_time = time.time()

        # 智能网络检测：先尝试在线模式，失败则切换离线模式
        import chromadb

        is_online = check_huggingface_connectivity(timeout=3.0)

        if not is_online:
            print("⚠️  网络连接异常，使用离线模式（预加载模型）继续测试...")
            # 在离线模式下，直接使用项目预加载的模型
            print(f"⏰ [{time.time()-start_test_time:.2f}s] 导入预加载模型...")
            from src.ai_rpg.embedding_model import multilingual_model

            print(f"✅ [{time.time()-start_test_time:.2f}s] 预加载模型导入完成")

            client = chromadb.Client()
            test_collection_name = "pytest_sentence_transformer_test"

            # 清理可能存在的测试集合
            try:
                client.delete_collection(test_collection_name)
            except Exception:
                pass

            try:
                print(f"⏰ [{time.time()-start_test_time:.2f}s] 创建集合...")
                collection = client.create_collection(test_collection_name)
                print(f"✅ [{time.time()-start_test_time:.2f}s] 集合创建完成")

                # 使用预加载模型计算embeddings
                print(f"⏰ [{time.time()-start_test_time:.2f}s] 计算文档embeddings...")
                documents = ["这是一个测试文档", "这是另一个测试文档"]
                embeddings = multilingual_model.encode(documents)
                print(f"✅ [{time.time()-start_test_time:.2f}s] Embeddings计算完成")

                # 添加文档
                print(f"⏰ [{time.time()-start_test_time:.2f}s] 添加文档...")
                collection.add(
                    embeddings=embeddings.tolist(),
                    documents=documents,
                    ids=["doc1", "doc2"],
                )
                print(f"✅ [{time.time()-start_test_time:.2f}s] 文档添加完成")

                # 查询相似文档
                print(f"⏰ [{time.time()-start_test_time:.2f}s] 查询相似文档...")
                query_text = "测试文档"
                query_embedding = multilingual_model.encode([query_text])
                results = collection.query(
                    query_embeddings=query_embedding.tolist(),
                    n_results=1,
                )
                print(f"✅ [{time.time()-start_test_time:.2f}s] 查询完成")

                assert results is not None
                assert "documents" in results
                assert results["documents"] is not None
                assert len(results["documents"]) > 0
                assert len(results["documents"][0]) > 0
                total_time = time.time() - start_test_time
                print(
                    f"✅ [{total_time:.2f}s] ChromaDB与Sentence Transformers集成测试成功（离线模式）"
                )
                print(f"📊 总耗时: {total_time:.2f}秒")
                print("=" * 60)
            finally:
                try:
                    client.delete_collection(test_collection_name)
                except Exception:
                    pass
            return

        # 在线模式：使用原有的 SentenceTransformerEmbeddingFunction
        print("🌐 使用在线模式进行测试")
        try:
            print(f"⏰ [{time.time()-start_test_time:.2f}s] 导入chromadb组件...")
            from chromadb.utils.embedding_functions import (
                SentenceTransformerEmbeddingFunction,
            )
            from src.ai_rpg.embedding_model import multilingual_model, is_model_cached

            print(f"✅ [{time.time()-start_test_time:.2f}s] 组件导入完成")

            model_name = "paraphrase-multilingual-MiniLM-L12-v2"
            print(f"📦 模型名称: {model_name}")

            # 检查模型是否已缓存
            print(f"⏰ [{time.time()-start_test_time:.2f}s] 检查模型缓存状态...")
            if is_model_cached(model_name):
                print(
                    f"✅ [{time.time()-start_test_time:.2f}s] 模型已缓存: {model_name}"
                )
                # 使用预加载的模型
                assert multilingual_model is not None, "预加载模型不可用"
                print(
                    f"⏰ [{time.time()-start_test_time:.2f}s] 开始创建embedding函数..."
                )
                # 使用预加载模型创建embedding函数
                ef = SentenceTransformerEmbeddingFunction(model_name=model_name)
                print(f"✅ [{time.time()-start_test_time:.2f}s] embedding函数创建完成")
            else:
                print(
                    f"⚠️ [{time.time()-start_test_time:.2f}s] 模型未缓存，将从网络下载: {model_name}"
                )
                # 创建embedding函数（使用轻量级模型进行测试）
                ef = SentenceTransformerEmbeddingFunction(model_name=model_name)
                print(
                    f"✅ [{time.time()-start_test_time:.2f}s] embedding函数创建完成（下载）"
                )

            print(f"⏰ [{time.time()-start_test_time:.2f}s] 创建ChromaDB客户端...")
            client = chromadb.Client()
            print(f"✅ [{time.time()-start_test_time:.2f}s] ChromaDB客户端创建完成")
            test_collection_name = "pytest_sentence_transformer_test"

            # 清理可能存在的测试集合
            try:
                client.delete_collection(test_collection_name)
            except Exception:
                pass

            try:
                # 创建使用sentence transformer的集合
                # from typing import Any

                print(
                    f"⏰ [{time.time()-start_test_time:.2f}s] 创建集合（带embedding函数）..."
                )
                collection = client.create_collection(
                    name=test_collection_name,
                    embedding_function=ef,  # type: ignore[arg-type]
                )
                print(f"✅ [{time.time()-start_test_time:.2f}s] 集合创建完成")

                # 添加文档（自动计算embedding）
                print(
                    f"⏰ [{time.time()-start_test_time:.2f}s] 开始添加文档（将自动计算embedding）..."
                )
                collection.add(
                    documents=["这是一个测试文档", "这是另一个测试文档"],
                    ids=["doc1", "doc2"],
                )
                print(f"✅ [{time.time()-start_test_time:.2f}s] 文档添加完成")

                # 查询相似文档
                print(f"⏰ [{time.time()-start_test_time:.2f}s] 开始查询相似文档...")
                results = collection.query(query_texts=["测试文档"], n_results=1)
                print(f"✅ [{time.time()-start_test_time:.2f}s] 查询完成")

                assert results is not None
                assert "documents" in results
                assert results["documents"] is not None
                assert len(results["documents"]) > 0
                assert len(results["documents"][0]) > 0
                total_time = time.time() - start_test_time
                print(
                    f"✅ [{total_time:.2f}s] ChromaDB与Sentence Transformers集成测试成功"
                )
                print(f"📊 总耗时: {total_time:.2f}秒")
                print("=" * 60)

            finally:
                # 清理测试集合
                try:
                    client.delete_collection(test_collection_name)
                except Exception:
                    pass

        except ImportError:
            pytest.skip("Sentence Transformers embedding function不可用")
        except Exception as e:
            pytest.fail(f"ChromaDB与Sentence Transformers集成测试失败: {e}")

    def test_project_model_loader_integration(self) -> None:
        """测试项目的预加载模型与ChromaDB集成"""
        print("\n" + "=" * 60)
        print("🔍 [TEST START] test_project_model_loader_integration")
        start_test_time = time.time()

        # 智能网络检测
        import os

        is_online = check_huggingface_connectivity(timeout=3.0)

        if not is_online:
            print("⚠️  网络连接异常，切换到离线模式继续测试...")
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
            os.environ["HF_HUB_OFFLINE"] = "1"
            print("📴 已启用离线模式")
        else:
            print("🌐 使用在线模式进行测试")
            os.environ.pop("TRANSFORMERS_OFFLINE", None)
            os.environ.pop("HF_HUB_OFFLINE", None)

        try:
            print(f"⏰ [{time.time()-start_test_time:.2f}s] 导入模块...")
            import chromadb
            from src.ai_rpg.embedding_model import (
                multilingual_model,
                SENTENCE_TRANSFORMERS_CACHE,
            )

            print(f"✅ [{time.time()-start_test_time:.2f}s] 模块导入完成")

            # 显示模型缓存目录
            print(f"✅ 模型缓存目录: {SENTENCE_TRANSFORMERS_CACHE}")

            # 使用项目的预加载多语言模型
            assert multilingual_model is not None, "预加载的多语言模型不可用"

            print(f"✅ 成功使用项目预加载的多语言模型")

            # 测试模型编码功能
            print(f"⏰ [{time.time()-start_test_time:.2f}s] 开始模型编码测试...")
            test_texts = ["这是测试文本", "another test text"]
            embeddings = multilingual_model.encode(test_texts)
            print(f"✅ [{time.time()-start_test_time:.2f}s] 模型编码完成")

            assert embeddings is not None
            assert len(embeddings) == 2
            print(f"✅ 模型编码测试成功，向量维度: {embeddings[0].shape}")

            # 测试与ChromaDB的集成
            client = chromadb.Client()
            test_collection_name = "pytest_preloaded_model_test"

            # 清理可能存在的测试集合
            try:
                client.delete_collection(test_collection_name)
            except Exception:
                pass

            try:
                # 创建集合（不使用embedding函数，手动提供embeddings）
                collection = client.create_collection(test_collection_name)

                # 使用预加载的模型计算embeddings
                documents = ["项目预加载模型测试文档1", "项目预加载模型测试文档2"]
                doc_embeddings = multilingual_model.encode(documents)

                # 添加文档和预计算的embeddings
                collection.add(
                    embeddings=doc_embeddings.tolist(),
                    documents=documents,
                    ids=["preloaded_model_doc1", "preloaded_model_doc2"],
                )

                # 查询相似文档
                query_text = "测试文档"
                query_embedding = multilingual_model.encode([query_text])

                results = collection.query(
                    query_embeddings=query_embedding.tolist(),
                    n_results=1,
                )

                assert results is not None
                assert "documents" in results
                assert results["documents"] is not None
                assert len(results["documents"]) > 0
                assert len(results["documents"][0]) > 0
                print("✅ 项目预加载模型与ChromaDB集成测试成功")

            finally:
                # 清理测试集合
                try:
                    client.delete_collection(test_collection_name)
                except Exception:
                    pass

        except ImportError as e:
            pytest.skip(f"无法导入项目预加载模型: {e}")
        except Exception as e:
            pytest.fail(f"项目预加载模型集成测试失败: {e}")


class TestChromaDBPerformance:
    """ChromaDB性能测试类"""

    def test_basic_performance(self) -> None:
        """基本性能测试"""
        import chromadb
        import time

        client = chromadb.Client()
        test_collection_name = "pytest_performance_test"

        # 清理可能存在的测试集合
        try:
            client.delete_collection(test_collection_name)
        except Exception:
            pass

        try:
            collection = client.create_collection(test_collection_name)

            # 测试批量添加性能
            start_time = time.time()

            batch_size = 100
            embeddings = [
                [float(i), float(i + 1), float(i + 2)] for i in range(batch_size)
            ]
            documents = [f"文档{i}" for i in range(batch_size)]
            ids = [f"id{i}" for i in range(batch_size)]

            collection.add(
                embeddings=cast("list[Sequence[float]]", embeddings),
                documents=documents,
                ids=ids,
            )

            add_time = time.time() - start_time
            print(f"✅ 批量添加{batch_size}条记录耗时: {add_time:.3f}秒")

            # 测试查询性能
            start_time = time.time()

            results = collection.query(
                query_embeddings=cast("list[Sequence[float]]", [[1.0, 2.0, 3.0]]),
                n_results=10,
            )

            query_time = time.time() - start_time
            print(f"✅ 查询耗时: {query_time:.3f}秒")

            assert add_time < 10.0, f"添加操作过慢: {add_time}秒"
            assert query_time < 1.0, f"查询操作过慢: {query_time}秒"

        finally:
            # 清理测试集合
            try:
                client.delete_collection(test_collection_name)
            except Exception:
                pass


if __name__ == "__main__":
    # 如果直接运行此文件，执行所有测试
    pytest.main([__file__, "-v"])
