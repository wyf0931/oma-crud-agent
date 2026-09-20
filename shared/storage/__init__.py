"""Shared TinyDB-backed application storage."""

from .database import get_database

__all__ = ["get_database"]
