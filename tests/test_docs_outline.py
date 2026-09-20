"""Tests for agent/docs/outline.py LLM outline generation."""

from unittest.mock import patch, MagicMock

import pytest

from agent.docs.schema import ProjectOutline
from agent.docs.outline import generate_outline


def _project_config():
    return {
        "project": {"name": "图书管理系统", "version": "V1.0"},
        "modules": [
            {"name": "BookManagement", "label": "图书管理", "description": "Manage books"},
            {"name": "UserManagement", "label": "用户管理", "description": "Manage users"},
        ],
        "fields": {},
    }


def _mock_llm_response_json():
    return """{
      "system_overview": "图书管理系统包括图书管理和用户管理两个核心模块。图书管理用于管理图书信息，用户管理用于管理后台账号。",
      "modules": [
        {"name": "BookManagement", "entity_name": "图书", "overview_sentence": "用于管理图书的入库、查询与下架。"},
        {"name": "UserManagement", "entity_name": "用户", "overview_sentence": "用于管理后台用户账号。"}
      ]
    }"""


@patch("agent.docs.outline.get_provider")
def test_generate_outline_returns_valid_project_outline(mock_get_provider):
    mock_provider = MagicMock()
    mock_provider.call_detailed.return_value = {
        "content": _mock_llm_response_json(),
        "thinking": None,
        "prompt": "...",
        "model": "gpt-4o-mini",
        "usage": {"total_tokens": 500},
        "duration_ms": 1200,
    }
    mock_get_provider.return_value = mock_provider

    result = generate_outline(_project_config())

    assert isinstance(result, ProjectOutline)
    assert "图书管理系统" in result.system_overview
    assert len(result.modules) == 2
    assert result.modules[0].name == "BookManagement"
    assert result.modules[0].entity_name == "图书"


@patch("agent.docs.outline.get_provider")
def test_generate_outline_fallback_on_llm_failure(mock_get_provider):
    """LLM raises -> return empty outline with error captured."""
    mock_provider = MagicMock()
    mock_provider.call_detailed.side_effect = RuntimeError("API timeout")
    mock_get_provider.return_value = mock_provider

    result, error = generate_outline(_project_config(), return_error=True)

    assert isinstance(result, ProjectOutline)
    assert result.system_overview == ""
    assert result.modules == []
    assert "API timeout" in error


@patch("agent.docs.outline.get_provider")
def test_generate_outline_fallback_on_invalid_json(mock_get_provider):
    """LLM returns non-JSON -> return empty outline."""
    mock_provider = MagicMock()
    mock_provider.call_detailed.return_value = {
        "content": "Sorry, I cannot help with that.",
        "thinking": None, "prompt": "", "model": "x", "usage": None, "duration_ms": 0,
    }
    mock_get_provider.return_value = mock_provider

    result, error = generate_outline(_project_config(), return_error=True)

    assert result.system_overview == ""
    assert error != ""


@patch("agent.docs.outline.get_provider")
def test_generate_outline_drops_modules_not_in_config(mock_get_provider):
    """If LLM hallucinates extra modules, drop them."""
    mock_provider = MagicMock()
    mock_provider.call_detailed.return_value = {
        "content": """{
          "system_overview": "x",
          "modules": [
            {"name": "BookManagement", "entity_name": "图书", "overview_sentence": "..."},
            {"name": "FakeModule", "entity_name": "假", "overview_sentence": "..."}
          ]
        }""",
        "thinking": None, "prompt": "", "model": "x", "usage": None, "duration_ms": 0,
    }
    mock_get_provider.return_value = mock_provider

    result = generate_outline(_project_config())

    names = [m.name for m in result.modules]
    assert "BookManagement" in names
    assert "FakeModule" not in names


@patch("agent.docs.outline.get_provider")
def test_generate_outline_fills_missing_modules_from_config(mock_get_provider):
    """If LLM skips a module, generate_outline should still return one entry per config module."""
    mock_provider = MagicMock()
    mock_provider.call_detailed.return_value = {
        "content": """{
          "system_overview": "x",
          "modules": [
            {"name": "BookManagement", "entity_name": "图书", "overview_sentence": "..."}
          ]
        }""",
        "thinking": None, "prompt": "", "model": "x", "usage": None, "duration_ms": 0,
    }
    mock_get_provider.return_value = mock_provider

    result = generate_outline(_project_config())

    names = [m.name for m in result.modules]
    assert "BookManagement" in names
    assert "UserManagement" in names  # backfilled from config
