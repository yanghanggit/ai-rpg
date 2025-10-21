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
from .config import PostgreSQLConfig, postgresql_config

# Import RAG operations from new rag module
from ..rag import load_knowledge_base_to_vector_db, search_similar_documents

__all__: List[str] = [
    # PostgreSQL configuration
    "PostgreSQLConfig",
    "postgresql_config",
    # Vector database models
    "VectorDocumentDB",
    # RAG operations (re-exported for backward compatibility)
    "load_knowledge_base_to_vector_db",
    "search_similar_documents",
    # Database clients and core utilities are exported via star imports
]
