"""
Comprehensive tests for sentence-transformers functionality.

This test suite ensures that sentence-transformers is properly installed
and functioning correctly in the current environment. It includes both
pytest-compatible unit tests and manual test functions for direct execution.
"""

import pytest
import numpy as np
import sys
from pathlib import Path
from typing import List


# Add src to path if needed for manual execution
src_path = Path(__file__).parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


class TestSentenceTransformersBasic:
    """Basic functionality tests for sentence-transformers."""

    def test_import_sentence_transformers(self):
        """Test that sentence-transformers can be imported successfully."""
        try:
            import sentence_transformers
            from sentence_transformers import SentenceTransformer
            from sentence_transformers.util import cos_sim
            assert True, "Successfully imported sentence-transformers"
        except ImportError as e:
            pytest.fail(f"Failed to import sentence-transformers: {e}")

    def test_load_model_basic(self):
        """Test loading a lightweight model."""
        from sentence_transformers import SentenceTransformer
        
        # 使用最轻量级的模型进行测试
        model_name = "all-MiniLM-L6-v2"
        
        try:
            model = SentenceTransformer(model_name)
            assert model is not None
            assert hasattr(model, 'encode')
        except Exception as e:
            pytest.fail(f"Failed to load model {model_name}: {e}")

    def test_encode_single_sentence(self):
        """Test encoding a single sentence."""
        from sentence_transformers import SentenceTransformer
        
        model = SentenceTransformer("all-MiniLM-L6-v2")
        
        test_sentence = "This is a test sentence."
        embedding = model.encode(test_sentence)
        
        assert isinstance(embedding, np.ndarray)
        assert len(embedding.shape) == 1  # 1D array for single sentence
        assert embedding.shape[0] > 0  # Non-empty embedding
        assert not np.isnan(embedding).any()  # No NaN values

    def test_encode_multiple_sentences(self):
        """Test encoding multiple sentences."""
        from sentence_transformers import SentenceTransformer
        
        model = SentenceTransformer("all-MiniLM-L6-v2")
        
        test_sentences = [
            "This is the first sentence.",
            "This is the second sentence.",
            "This is a completely different sentence."
        ]
        
        embeddings = model.encode(test_sentences)
        
        assert isinstance(embeddings, np.ndarray)
        assert len(embeddings.shape) == 2  # 2D array for multiple sentences
        assert embeddings.shape[0] == len(test_sentences)
        assert embeddings.shape[1] > 0  # Non-empty embeddings
        assert not np.isnan(embeddings).any()  # No NaN values

    def test_similarity_computation(self):
        """Test computing similarity between sentences."""
        from sentence_transformers import SentenceTransformer
        from sentence_transformers.util import cos_sim
        
        model = SentenceTransformer("all-MiniLM-L6-v2")
        
        # Similar sentences
        sentence1 = "The cat is sleeping on the mat."
        sentence2 = "A cat is lying on a mat."
        
        # Different sentence
        sentence3 = "The weather is very nice today."
        
        embeddings = model.encode([sentence1, sentence2, sentence3])
        
        # Compute similarities
        sim_1_2 = cos_sim(embeddings[0], embeddings[1])
        sim_1_3 = cos_sim(embeddings[0], embeddings[2])
        
        # Extract scalar values from tensors
        sim_1_2_value = sim_1_2.item()
        sim_1_3_value = sim_1_3.item()
        
        # Similar sentences should have higher similarity
        assert sim_1_2_value > sim_1_3_value
        assert -1 <= sim_1_2_value <= 1  # Cosine similarity should be between -1 and 1
        assert -1 <= sim_1_3_value <= 1


class TestSentenceTransformersGameContext:
    """Tests for sentence-transformers with game-specific content."""

    @pytest.fixture
    def game_knowledge_base(self) -> List[str]:
        """Sample game knowledge base for testing."""
        return [
            "艾尔法尼亚大陆分为三大王国：人类的阿斯特拉王国、精灵的月桂森林联邦、兽人的铁爪部族联盟。",
            "晨曦之刃是传说中的圣剑，剑身由星辰钢打造，剑柄镶嵌着光明神的眼泪结晶。",
            "黑暗魔王阿巴顿曾经统治艾尔法尼亚大陆，将其变成死亡与绝望的土地。",
            "人类以阿斯特拉王国为中心，擅长锻造和贸易，他们的骑士团以重甲和长剑闻名。",
            "精灵居住在月桂森林，寿命可达千年，是最优秀的弓箭手和自然魔法师。",
            "失落的贤者之塔：古代魔法师的研究所，内藏强大的魔法道具和禁忌知识。",
        ]

    def test_chinese_text_encoding(self, game_knowledge_base):
        """Test encoding Chinese game content."""
        from sentence_transformers import SentenceTransformer
        
        # 使用支持多语言的模型
        model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        
        embeddings = model.encode(game_knowledge_base)
        
        assert isinstance(embeddings, np.ndarray)
        assert embeddings.shape[0] == len(game_knowledge_base)
        assert embeddings.shape[1] > 0
        assert not np.isnan(embeddings).any()

    def test_semantic_search_simulation(self, game_knowledge_base):
        """Test simulating semantic search functionality."""
        from sentence_transformers import SentenceTransformer
        from sentence_transformers.util import cos_sim
        
        model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        
        # Encode knowledge base
        kb_embeddings = model.encode(game_knowledge_base)
        
        # Test queries
        queries = [
            "圣剑的信息",  # Should match info about 晨曦之刃
            "王国有哪些",  # Should match info about kingdoms
            "精灵的特点",  # Should match info about elves
        ]
        
        for query in queries:
            query_embedding = model.encode([query])
            similarities = cos_sim(query_embedding, kb_embeddings)[0]
            
            # Find most similar document
            best_match_idx = similarities.argmax().item()
            best_similarity = similarities[best_match_idx].item()
            
            assert 0 <= best_similarity <= 1
            assert best_match_idx < len(game_knowledge_base)
            
            # The similarity should be reasonable (> 0.1 for related content)
            assert best_similarity > 0.1, f"Query '{query}' has low similarity ({best_similarity})"

    def test_document_ranking(self, game_knowledge_base):
        """Test ranking documents by relevance."""
        from sentence_transformers import SentenceTransformer
        from sentence_transformers.util import cos_sim
        
        model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        
        # Encode knowledge base
        kb_embeddings = model.encode(game_knowledge_base)
        
        # Query about sword/weapon
        query = "武器和剑的信息"
        query_embedding = model.encode([query])
        
        similarities = cos_sim(query_embedding, kb_embeddings)[0]
        
        # Get top 3 most relevant documents
        top_indices = similarities.argsort(descending=True)[:3]
        top_similarities = similarities[top_indices]
        
        # Check that similarities are in descending order
        for i in range(len(top_similarities) - 1):
            assert top_similarities[i] >= top_similarities[i + 1]
        
        # The top result should be reasonably relevant
        assert top_similarities[0] > 0.2


class TestSentenceTransformersPerformance:
    """Performance and resource usage tests."""

    def test_model_memory_usage(self):
        """Test that model loading doesn't consume excessive memory."""
        import psutil
        import os
        from sentence_transformers import SentenceTransformer
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Load model
        model = SentenceTransformer("all-MiniLM-L6-v2")
        
        # Get memory after loading
        after_load_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        memory_increase = after_load_memory - initial_memory
        
        # Model should not consume more than 500MB (reasonable limit)
        assert memory_increase < 500, f"Model consumed too much memory: {memory_increase:.2f}MB"

    def test_encoding_speed(self):
        """Test encoding speed for reasonable performance."""
        import time
        from sentence_transformers import SentenceTransformer
        
        model = SentenceTransformer("all-MiniLM-L6-v2")
        
        # Test sentences
        sentences = [f"This is test sentence number {i}." for i in range(100)]
        
        # Measure encoding time
        start_time = time.time()
        embeddings = model.encode(sentences)
        end_time = time.time()
        
        encoding_time = end_time - start_time
        sentences_per_second = len(sentences) / encoding_time
        
        # Should be able to encode at least 10 sentences per second
        assert sentences_per_second > 10, f"Encoding too slow: {sentences_per_second:.2f} sentences/sec"


class TestSentenceTransformersErrorHandling:
    """Test error handling and edge cases."""

    def test_empty_input(self):
        """Test handling of empty input."""
        from sentence_transformers import SentenceTransformer
        
        model = SentenceTransformer("all-MiniLM-L6-v2")
        
        # Empty string
        embedding = model.encode("")
        assert isinstance(embedding, np.ndarray)
        assert embedding.shape[0] > 0
        
        # Empty list
        embeddings = model.encode([])
        assert isinstance(embeddings, np.ndarray)
        assert embeddings.shape[0] == 0

    def test_very_long_text(self):
        """Test handling of very long text."""
        from sentence_transformers import SentenceTransformer
        
        model = SentenceTransformer("all-MiniLM-L6-v2")
        
        # Very long text (beyond typical token limits)
        long_text = "This is a test sentence. " * 1000
        
        try:
            embedding = model.encode(long_text)
            assert isinstance(embedding, np.ndarray)
            assert embedding.shape[0] > 0
        except Exception as e:
            # If it fails, it should fail gracefully
            assert "token" in str(e).lower() or "length" in str(e).lower()

    def test_special_characters(self):
        """Test handling of special characters and mixed languages."""
        from sentence_transformers import SentenceTransformer
        
        model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        
        special_texts = [
            "Hello 世界! 🌍",
            "Special chars: @#$%^&*()",
            "Numbers: 123456789",
            "Émojis and açcénts",
            "🚀🎮🏆⚔️🛡️",
        ]
        
        for text in special_texts:
            embedding = model.encode(text)
            assert isinstance(embedding, np.ndarray)
            assert embedding.shape[0] > 0
            assert not np.isnan(embedding).any()


if __name__ == "__main__":
    # Manual test functions for direct execution
    def test_basic_functionality():
        """Test basic sentence-transformers functionality."""
        print("=" * 60)
        print("Testing sentence-transformers Basic Functionality")
        print("=" * 60)
        
        try:
            # Test 1: Import
            print("1. Testing import...")
            from sentence_transformers import SentenceTransformer
            from sentence_transformers.util import cos_sim
            print("✅ Import successful")
            
            # Test 2: Load model
            print("\n2. Testing model loading...")
            model = SentenceTransformer("all-MiniLM-L6-v2")
            print("✅ Model loaded successfully")
            
            # Test 3: Encode single sentence
            print("\n3. Testing single sentence encoding...")
            sentence = "This is a test sentence."
            embedding = model.encode(sentence)
            print(f"✅ Encoded sentence: '{sentence}'")
            print(f"   Embedding shape: {embedding.shape}")
            print(f"   Embedding type: {type(embedding)}")
            
            # Test 4: Encode multiple sentences
            print("\n4. Testing multiple sentence encoding...")
            sentences = [
                "This is the first sentence.",
                "This is the second sentence.",
                "This is a different sentence."
            ]
            embeddings = model.encode(sentences)
            print(f"✅ Encoded {len(sentences)} sentences")
            print(f"   Embeddings shape: {embeddings.shape}")
            
            # Test 5: Similarity computation
            print("\n5. Testing similarity computation...")
            sim_1_2 = cos_sim(embeddings[0], embeddings[1])
            sim_1_3 = cos_sim(embeddings[0], embeddings[2])
            print(f"✅ Similarity between sentence 1 and 2: {sim_1_2.item():.4f}")
            print(f"✅ Similarity between sentence 1 and 3: {sim_1_3.item():.4f}")
            
            return True
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def test_game_context():
        """Test with game-specific content."""
        print("\n" + "=" * 60)
        print("Testing Game Context Functionality")
        print("=" * 60)
        
        try:
            from sentence_transformers import SentenceTransformer
            from sentence_transformers.util import cos_sim
            import numpy as np
            
            # Use multilingual model for Chinese content
            print("1. Loading multilingual model...")
            model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
            print("✅ Multilingual model loaded")
            
            # Game knowledge base
            knowledge_base = [
                "艾尔法尼亚大陆分为三大王国：人类的阿斯特拉王国、精灵的月桂森林联邦、兽人的铁爪部族联盟。",
                "晨曦之刃是传说中的圣剑，剑身由星辰钢打造，剑柄镶嵌着光明神的眼泪结晶。",
                "黑暗魔王阿巴顿曾经统治艾尔法尼亚大陆，将其变成死亡与绝望的土地。",
                "人类以阿斯特拉王国为中心，擅长锻造和贸易，他们的骑士团以重甲和长剑闻名。",
                "精灵居住在月桂森林，寿命可达千年，是最优秀的弓箭手和自然魔法师。",
            ]
            
            print(f"\n2. Encoding knowledge base ({len(knowledge_base)} documents)...")
            kb_embeddings = model.encode(knowledge_base)
            print(f"✅ Knowledge base encoded: {kb_embeddings.shape}")
            
            # Test queries
            queries = [
                "圣剑的信息",
                "王国有哪些",
                "精灵的特点",
            ]
            
            print(f"\n3. Testing semantic search with {len(queries)} queries...")
            for i, query in enumerate(queries):
                print(f"\n   Query {i+1}: '{query}'")
                query_embedding = model.encode([query])
                similarities = cos_sim(query_embedding, kb_embeddings)[0]
                
                # Find best match
                best_idx = similarities.argmax().item()
                best_sim = similarities[best_idx].item()
                
                print(f"   Best match (similarity: {best_sim:.4f}):")
                print(f"   '{knowledge_base[best_idx][:50]}...'")
            
            print("✅ Semantic search functionality working correctly")
            return True
            
        except Exception as e:
            print(f"❌ Game context test failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def test_performance():
        """Test basic performance metrics."""
        print("\n" + "=" * 60)
        print("Testing Performance")
        print("=" * 60)
        
        try:
            import time
            from sentence_transformers import SentenceTransformer
            
            print("1. Testing encoding speed...")
            model = SentenceTransformer("all-MiniLM-L6-v2")
            
            # Test sentences
            test_sentences = [f"This is test sentence number {i}." for i in range(50)]
            
            start_time = time.time()
            embeddings = model.encode(test_sentences)
            end_time = time.time()
            
            encoding_time = end_time - start_time
            sentences_per_second = len(test_sentences) / encoding_time
            
            print(f"✅ Encoded {len(test_sentences)} sentences in {encoding_time:.2f} seconds")
            print(f"✅ Speed: {sentences_per_second:.2f} sentences/second")
            
            if sentences_per_second > 5:  # Reasonable threshold
                print("✅ Performance is acceptable")
            else:
                print("⚠️  Performance might be slow but functional")
                
            return True
            
        except Exception as e:
            print(f"❌ Performance test failed: {e}")
            return False

    def run_manual_tests():
        """Run all manual tests."""
        print("Starting sentence-transformers comprehensive test suite...")
        print(f"Python version: {sys.version}")
        print(f"Test script location: {__file__}")
        
        tests = [
            ("Basic Functionality", test_basic_functionality),
            ("Game Context", test_game_context),
            ("Performance", test_performance),
        ]
        
        results = {}
        for test_name, test_func in tests:
            print(f"\n{'='*80}")
            print(f"Running {test_name} Tests")
            print(f"{'='*80}")
            
            try:
                results[test_name] = test_func()
            except Exception as e:
                print(f"❌ {test_name} test suite failed with exception: {e}")
                results[test_name] = False
        
        # Summary
        print(f"\n{'='*80}")
        print("TEST SUMMARY")
        print(f"{'='*80}")
        
        all_passed = True
        for test_name, passed in results.items():
            status = "✅ PASSED" if passed else "❌ FAILED"
            print(f"{test_name:20}: {status}")
            if not passed:
                all_passed = False
        
        print(f"\n{'='*80}")
        if all_passed:
            print("🎉 ALL TESTS PASSED! sentence-transformers is ready for integration.")
        else:
            print("⚠️  Some tests failed. Please check the output above.")
        print(f"{'='*80}")
        
        return all_passed

    # Determine execution mode
    if len(sys.argv) > 1 and sys.argv[1] == "--manual":
        # Manual test mode
        success = run_manual_tests()
        sys.exit(0 if success else 1)
    else:
        # Basic smoke test when executed directly without arguments
        print("Running sentence-transformers smoke test...")
        print("Use --manual flag for comprehensive manual tests")
        
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer("all-MiniLM-L6-v2")
            
            test_sentence = "Hello, world!"
            embedding = model.encode(test_sentence)
            
            print(f"✅ Successfully encoded sentence: '{test_sentence}'")
            print(f"✅ Embedding shape: {embedding.shape}")
            print(f"✅ Embedding sample: {embedding[:5]}")
            print("✅ Basic smoke test passed!")
            print("\n💡 Run with --manual flag for comprehensive testing:")
            print(f"   python {__file__} --manual")
            
        except Exception as e:
            print(f"❌ Smoke test failed: {e}")
            sys.exit(1)
