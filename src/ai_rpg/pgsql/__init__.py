"""
Database access layer for the nirva_service application.
"""

from typing import List
from .base import *
from .client import *
from .user import *
from .vector_document import VectorDocumentDB
from .vector_document_operations import save_vector_document, search_similar_documents
from .config import PostgreSQLConfig, postgresql_config


__all__: List[str] = [
    # PostgreSQL configuration
    "PostgreSQLConfig",
    "postgresql_config",
    # Database management functions
    "pgsql_database_exists",
    "pgsql_create_database",
    "pgsql_drop_database",
    "pgsql_ensure_database_tables",
    # Vector database models
    "VectorDocumentDB",
    # Vector document operations (low-level)
    "save_vector_document",
    "search_similar_documents",
]
