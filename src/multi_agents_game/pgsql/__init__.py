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

# Import RAG operations from new rag module
from ..rag import initialize_rag_system, rag_semantic_search

__all__: List[str] = [
    # Vector database models
    "VectorDocumentDB",
    # RAG operations (re-exported for backward compatibility)
    "initialize_rag_system",
    "rag_semantic_search",
    # Database clients and core utilities are exported via star imports
]
