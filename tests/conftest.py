"""Shared test fixtures for code generation tests."""

import ast
import random
import secrets
import string
import tempfile
from pathlib import Path

import pytest

from oma_info_system.generation.generator import CodeGenerator


def _make_code() -> str:
    code_chars = string.ascii_lowercase + string.digits
    return "".join(random.choices(code_chars[:5], k=5))


@pytest.fixture
def sample_config():
    """Single module with varied field types."""
    return {
        "project": {
            "code": _make_code(),
            "name": "Book Management System",
            "version": "V1.0",
            "theme": "yeti",
            "author": "Test Author",
            "secret_key": secrets.token_hex(32),
            "admin_account": "admin",
            "admin_password": "test123",
        },
        "modules": [
            {"name": "BookInfo", "label": "图书信息", "description": "Manage books"},
        ],
        "fields": {
            "BookInfo": [
                {"name": "title", "type": "String", "required": True, "can_search": True},
                {"name": "author", "type": "String", "required": False, "can_search": True},
                {"name": "isbn", "type": "String", "required": True, "can_search": False},
                {"name": "pages", "type": "Integer", "required": False, "can_search": False},
                {"name": "price", "type": "Float", "required": False, "can_search": False},
                {"name": "description", "type": "Text", "required": False, "can_search": False},
                {"name": "published_date", "type": "Date", "required": False, "can_search": False},
                {"name": "in_stock", "type": "Boolean", "required": False, "can_search": False},
            ],
        },
    }


@pytest.fixture
def multi_module_config():
    """Multiple modules config."""
    return {
        "project": {
            "code": _make_code(),
            "name": "School Admin",
            "version": "V1.0",
            "theme": "cerulean",
            "author": "Test",
            "secret_key": secrets.token_hex(32),
            "admin_account": "admin",
            "admin_password": "admin123",
        },
        "modules": [
            {"name": "Student", "label": "学生管理", "description": "Manage students"},
            {"name": "Course", "label": "课程管理", "description": "Manage courses"},
            {"name": "Teacher", "label": "教师管理", "description": "Manage teachers"},
        ],
        "fields": {
            "Student": [
                {"name": "name", "type": "String", "required": True, "can_search": True},
                {"name": "grade", "type": "Integer", "required": False, "can_search": False},
            ],
            "Course": [
                {"name": "title", "type": "String", "required": True, "can_search": True},
                {"name": "credits", "type": "Integer", "required": False, "can_search": False},
            ],
            "Teacher": [
                {"name": "name", "type": "String", "required": True, "can_search": True},
                {"name": "subject", "type": "String", "required": False, "can_search": True},
            ],
        },
    }


@pytest.fixture
def empty_modules_config():
    """Config with no business modules, just User."""
    return {
        "project": {
            "code": _make_code(),
            "name": "Minimal System",
            "version": "V1.0",
            "theme": "yeti",
            "author": "Test",
            "secret_key": secrets.token_hex(32),
            "admin_account": "admin",
            "admin_password": "admin123",
        },
        "modules": [],
        "fields": {},
    }


@pytest.fixture
def generator():
    """CodeGenerator with default templates."""
    return CodeGenerator()


@pytest.fixture
def generated_project(generator, sample_config):
    """Generate a project and return its path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = generator.generate(sample_config, tmpdir)
        yield Path(path)


@pytest.fixture
def generated_multi_project(generator, multi_module_config):
    """Generate multi-module project."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = generator.generate(multi_module_config, tmpdir)
        yield Path(path)


@pytest.fixture
def generated_empty_project(generator, empty_modules_config):
    """Generate empty project."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = generator.generate(empty_modules_config, tmpdir)
        yield Path(path)


# Helper to parse Python source to AST
def parse_python(filepath: Path) -> ast.Module:
    return ast.parse(filepath.read_text())
