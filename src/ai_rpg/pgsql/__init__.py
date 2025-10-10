"""
Database access layer for the nirva_service application.

This module provides:
- Database clients (PostgreSQL)
- ORM models and mappings
- Database utilities and helpers
- Data access objects (DAOs)
"""

from typing import List

from .base import *
from .client import *
from .user import *
from .vector_document import VectorDocumentDB
from .config import PostgresConfig, DEFAULT_POSTGRES_CONFIG

# Import RAG operations from new rag module
from ..rag import load_knowledge_base_to_vector_db, rag_semantic_search

__all__: List[str] = [
    # PostgreSQL configuration
    "PostgresConfig",
    "DEFAULT_POSTGRES_CONFIG",
    # Vector database models
    "VectorDocumentDB",
    # RAG operations (re-exported for backward compatibility)
    "load_knowledge_base_to_vector_db",
    "rag_semantic_search",
    # Database clients and core utilities are exported via star imports
]
