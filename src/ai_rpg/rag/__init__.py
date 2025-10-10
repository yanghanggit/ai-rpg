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

from .rag_system import (
    # _prepare_documents_for_vector_storage,
    load_knowledge_base_to_vector_db,
    rag_semantic_search,
)

# Import routing components for convenience
from .routing import (
    KeywordRouteStrategy,
    RouteConfigBuilder,
    RouteDecision,
    RouteDecisionManager,
    RouteStrategy,
    SemanticRouteStrategy,
    StrategyWeight,
    create_route_manager_with_strategies,
)

__all__: List[str] = [
    # RAG core functions
    # "_prepare_documents_for_vector_storage",
    "load_knowledge_base_to_vector_db",
    "rag_semantic_search",
    # Routing components
    "RouteStrategy",
    "RouteDecision",
    "KeywordRouteStrategy",
    "SemanticRouteStrategy",
    "RouteDecisionManager",
    "StrategyWeight",
    "RouteConfigBuilder",
    "create_route_manager_with_strategies",
]
