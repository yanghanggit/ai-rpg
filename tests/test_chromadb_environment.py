"""ChromaDB 环境测试。

使用项目预加载的多语言模型（paraphrase-multilingual-MiniLM-L12-v2）验证：
1. 模型缓存目录存在
2. 模型可加载并可编码
3. ChromaDB 存储与语义检索可用
"""

from pathlib import Path

import chromadb
import requests

from src.ai_rpg.embedding_model import multilingual_model

# 模型缓存路径，与 src/ai_rpg/embedding_model/sentence_transformer.py 保持一致
cache_model_path = (
    Path(".sentence_transformers") / "paraphrase-multilingual-MiniLM-L12-v2"
)


def check_huggingface_connectivity(timeout: float = 5.0) -> bool:
    """检测 HuggingFace 网络连通性。"""
    try:
        response = requests.head(
            "https://huggingface.co", timeout=timeout, allow_redirects=True
        )
        return response.status_code < 500
    except requests.Timeout:
        return False
    except requests.ConnectionError:
        return False
    except Exception:
        return False


class TestChromaDBEnvironment:
    """基于项目预加载多语言模型的 ChromaDB 环境测试。"""

    def test_model_cache_exists(self) -> None:
        """模型缓存目录应存在。"""
        assert cache_model_path.exists(), f"模型缓存不存在: {cache_model_path}"

    def test_model_encodes(self) -> None:
        """多语言模型应能对中英文文本编码。"""
        texts = ["这是一个测试文档", "another test document"]
        embeddings = multilingual_model.encode(texts)
        assert embeddings.shape[0] == len(texts)

    def test_chromadb_add_and_query(self) -> None:
        """使用多语言模型完成 ChromaDB 写入与语义检索。"""
        client = chromadb.Client()
        collection_name = "pytest_chromadb_environment"

        try:
            client.delete_collection(collection_name)
        except Exception:
            pass

        try:
            collection = client.create_collection(collection_name)

            documents = ["这是一个测试文档", "这是另一个测试文档"]
            embeddings = multilingual_model.encode(documents)
            collection.add(
                embeddings=embeddings.tolist(),
                documents=documents,
                ids=["doc1", "doc2"],
            )

            query_embedding = multilingual_model.encode(["测试文档"])
            results = collection.query(
                query_embeddings=query_embedding.tolist(),
                n_results=1,
            )

            docs = results["documents"]
            assert docs is not None
            assert len(docs[0]) > 0
        finally:
            try:
                client.delete_collection(collection_name)
            except Exception:
                pass
