#!/usr/bin/env python3
"""
ChromaDB环境测试
测试ChromaDB的基本功能和集成状态
"""

import pytest
from typing import List as ListType, cast
from collections.abc import Sequence


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
        try:
            import chromadb
            from chromadb.utils.embedding_functions import (
                SentenceTransformerEmbeddingFunction,
            )

            # 导入项目的模型加载器
            from src.ai_rpg.embedding_model.model_loader import (
                load_sentence_transformer,
                is_model_cached,
            )

            model_name = "all-MiniLM-L6-v2"

            # 检查模型是否已缓存
            if is_model_cached(model_name):
                print(f"✅ 使用项目缓存的模型: {model_name}")
                # 使用项目的模型加载器加载模型
                model = load_sentence_transformer(model_name)
                if model is None:
                    pytest.fail(f"无法从缓存加载模型: {model_name}")
                # 使用已加载的模型创建embedding函数
                ef = SentenceTransformerEmbeddingFunction(model_name=model_name)
            else:
                print(f"⚠️ 模型未缓存，将从网络下载: {model_name}")
                # 创建embedding函数（使用轻量级模型进行测试）
                ef = SentenceTransformerEmbeddingFunction(model_name=model_name)

            client = chromadb.Client()
            test_collection_name = "pytest_sentence_transformer_test"

            # 清理可能存在的测试集合
            try:
                client.delete_collection(test_collection_name)
            except Exception:
                pass

            try:
                # 创建使用sentence transformer的集合
                from typing import Any

                collection = client.create_collection(
                    name=test_collection_name,
                    embedding_function=ef,  # type: ignore[arg-type]
                )

                # 添加文档（自动计算embedding）
                collection.add(
                    documents=["这是一个测试文档", "这是另一个测试文档"],
                    ids=["doc1", "doc2"],
                )

                # 查询相似文档
                results = collection.query(query_texts=["测试文档"], n_results=1)

                assert results is not None
                assert "documents" in results
                assert results["documents"] is not None
                assert len(results["documents"]) > 0
                assert len(results["documents"][0]) > 0
                print("✅ ChromaDB与Sentence Transformers集成测试成功")

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
        """测试项目的ModelLoader与ChromaDB集成"""
        try:
            import chromadb
            from src.ai_rpg.embedding_model.model_loader import (
                load_multilingual_model,
                is_model_cached,
                get_model_loader,
            )

            # 获取模型加载器
            loader = get_model_loader()
            print(f"✅ 模型缓存目录: {loader.cache_dir}")

            # 使用项目的多语言模型加载器
            model = load_multilingual_model()
            if model is None:
                pytest.skip("多语言模型未缓存，请先运行下载脚本")

            print(f"✅ 成功从项目缓存加载多语言模型")

            # 测试模型编码功能
            test_texts = ["这是测试文本", "another test text"]
            embeddings = model.encode(test_texts)

            assert embeddings is not None
            assert len(embeddings) == 2
            print(f"✅ 模型编码测试成功，向量维度: {embeddings[0].shape}")

            # 测试与ChromaDB的集成
            client = chromadb.Client()
            test_collection_name = "pytest_model_loader_test"

            # 清理可能存在的测试集合
            try:
                client.delete_collection(test_collection_name)
            except Exception:
                pass

            try:
                # 创建集合（不使用embedding函数，手动提供embeddings）
                collection = client.create_collection(test_collection_name)

                # 使用加载的模型计算embeddings
                documents = ["项目缓存模型测试文档1", "项目缓存模型测试文档2"]
                doc_embeddings = model.encode(documents)

                # 添加文档和预计算的embeddings
                collection.add(
                    embeddings=doc_embeddings.tolist(),
                    documents=documents,
                    ids=["cached_model_doc1", "cached_model_doc2"],
                )

                # 查询相似文档
                query_text = "测试文档"
                query_embedding = model.encode([query_text])

                results = collection.query(
                    query_embeddings=query_embedding.tolist(),
                    n_results=1,
                )

                assert results is not None
                assert "documents" in results
                assert results["documents"] is not None
                assert len(results["documents"]) > 0
                assert len(results["documents"][0]) > 0
                print("✅ 项目ModelLoader与ChromaDB集成测试成功")

            finally:
                # 清理测试集合
                try:
                    client.delete_collection(test_collection_name)
                except Exception:
                    pass

        except ImportError as e:
            pytest.skip(f"无法导入项目模型加载器: {e}")
        except Exception as e:
            pytest.fail(f"项目ModelLoader集成测试失败: {e}")


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
