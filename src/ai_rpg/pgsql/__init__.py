"""
Database access layer for the nirva_service application.
"""

from typing import List

from .base import *
from .card_prototype import CardPrototypeDB
from .card_prototype_operations import (
    get_card_prototype,
    get_card_prototype_by_name,
    list_card_prototype_index,
    save_card_prototype,
)
from .client import *
from .config import PostgreSQLConfig, postgresql_config
from .deck_build import DeckBuildDB
from .deck_build_operations import get_default_deck_card_jsons, save_deck_build
from .procrastinate_app import procrastinate_app
from .task_error import TaskErrorDB
from .task_error_operations import get_task_error, save_task_error
from .user import *
from .vector_document import VectorDocumentDB
from .vector_document_operations import save_vector_document, search_similar_documents

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
    # Card prototype models
    "CardPrototypeDB",
    # Card prototype operations
    "save_card_prototype",
    "list_card_prototype_index",
    "get_card_prototype",
    "get_card_prototype_by_name",
    # Deck build models
    "DeckBuildDB",
    # Deck build operations
    "save_deck_build",
    "get_default_deck_card_jsons",
    # Task error models
    "TaskErrorDB",
    # Task error operations
    "save_task_error",
    "get_task_error",
    # Procrastinate task queue app
    "procrastinate_app",
]
