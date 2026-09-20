"""Tests for agent/docs/schema.py Pydantic models."""

import pytest
from pydantic import ValidationError

from agent.docs.schema import ModuleOutline, ProjectOutline


def test_module_outline_minimum_fields():
    m = ModuleOutline(name="BookManagement", entity_name="图书", overview_sentence="...")
    assert m.name == "BookManagement"
    assert m.entity_name == "图书"


def test_module_outline_requires_name():
    with pytest.raises(ValidationError):
        ModuleOutline(entity_name="图书", overview_sentence="...")


def test_project_outline_with_modules():
    p = ProjectOutline(
        system_overview="系统包括图书管理。",
        modules=[
            ModuleOutline(name="BookManagement", entity_name="图书", overview_sentence="..."),
            ModuleOutline(name="UserManagement", entity_name="用户", overview_sentence="..."),
        ],
    )
    assert len(p.modules) == 2
    assert p.modules[0].name == "BookManagement"


def test_project_outline_requires_system_overview():
    with pytest.raises(ValidationError):
        ProjectOutline(modules=[])


def test_project_outline_empty_modules_allowed():
    """Edge case: project with zero business modules is still valid."""
    p = ProjectOutline(system_overview="minimal", modules=[])
    assert p.modules == []
