"""
RAG (Retrieval-Augmented Generation) module

This module provides RAG system functionality including:
1. RAG system initialization and setup
2. Semantic search and document retrieval
3. Knowledge base management and embeddings
4. Routing decision strategies for RAG system

Main components:
- rag_system: Core RAG operations and system management
- routing: RAG routing decision strategies and management
"""

from typing import List

from .knowledge_retrieval import (
    load_knowledge_base_to_vector_db,
    search_similar_documents,
    load_character_private_knowledge,
    search_private_knowledge,
)

__all__: List[str] = [
    "load_knowledge_base_to_vector_db",
    "search_similar_documents",
    "load_character_private_knowledge",
    "search_private_knowledge",
]
