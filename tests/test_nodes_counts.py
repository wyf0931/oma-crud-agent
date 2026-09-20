"""Tests for module/field count constraint handling in requirements + generation nodes."""

from unittest.mock import patch, MagicMock

from agent.state.types import AgentState
from agent.nodes.generation import _normalize_field


def test_normalize_field_accepts_camel_case_search_flag():
    assert _normalize_field({"name": "name", "canSearch": True})["can_search"] is True
    assert _normalize_field({"name": "name", "canSearch": False})["can_search"] is False


def _base_state(user_input: str = "生成图书管理系统") -> AgentState:
    return {  # type: ignore[return-value]
        "user_input": user_input,
        "mode": "yolo",
        "output_dir": "/tmp/x",
        "current_step": "",
        "step_history": [],
        "step_details": {},
        "review_issues": [],
        "review_fixes": [],
        "retry_count": 0,
    }


# ----- understand_requirements -----

@patch("agent.nodes.requirements.get_provider")
def test_understand_requirements_extracts_explicit_module_max(mock_get_provider):
    from agent.nodes.requirements import understand_requirements

    mock_provider = MagicMock()
    mock_provider.call_detailed.return_value = {
        "content": '{"project_name":"图书管理系统","business_domain":"图书馆","features":[],"module_count_max":4,"field_count_max":12}',
        "thinking": None, "prompt": "", "model": "x", "usage": None, "duration_ms": 0,
    }
    mock_get_provider.return_value = mock_provider

    state = _base_state("生成图书管理系统，不超过 4 个模块，每个模块不超过 12 个字段")
    result = understand_requirements(state)

    assert result["module_count_max"] == 4
    assert result["field_count_max"] == 12


@patch("agent.nodes.requirements.get_provider")
def test_understand_requirements_defaults_to_none_when_unspecified(mock_get_provider):
    from agent.nodes.requirements import understand_requirements

    mock_provider = MagicMock()
    mock_provider.call_detailed.return_value = {
        "content": '{"project_name":"图书管理系统","business_domain":"图书馆","features":[]}',
        "thinking": None, "prompt": "", "model": "x", "usage": None, "duration_ms": 0,
    }
    mock_get_provider.return_value = mock_provider

    result = understand_requirements(_base_state("生成图书管理系统"))

    assert result["module_count_max"] is None
    assert result["field_count_max"] is None


@patch("agent.nodes.requirements.get_provider")
def test_understand_requirements_coerces_string_counts(mock_get_provider):
    """LLM may return counts as strings — coerce to int."""
    from agent.nodes.requirements import understand_requirements

    mock_provider = MagicMock()
    mock_provider.call_detailed.return_value = {
        "content": '{"project_name":"X","business_domain":"X","features":[],"module_count_max":"5","field_count_max":"10"}',
        "thinking": None, "prompt": "", "model": "x", "usage": None, "duration_ms": 0,
    }
    mock_get_provider.return_value = mock_provider

    result = understand_requirements(_base_state())

    assert result["module_count_max"] == 5
    assert result["field_count_max"] == 10


@patch("agent.nodes.requirements.get_provider")
def test_understand_requirements_rejects_non_positive_counts(mock_get_provider):
    """Zero or negative counts make no sense — fall back to None."""
    from agent.nodes.requirements import understand_requirements

    mock_provider = MagicMock()
    mock_provider.call_detailed.return_value = {
        "content": '{"project_name":"X","business_domain":"X","features":[],"module_count_max":0,"field_count_max":-3}',
        "thinking": None, "prompt": "", "model": "x", "usage": None, "duration_ms": 0,
    }
    mock_get_provider.return_value = mock_provider

    result = understand_requirements(_base_state())

    assert result["module_count_max"] is None
    assert result["field_count_max"] is None


@patch("agent.nodes.requirements.get_provider")
def test_understand_requirements_resets_counts_on_llm_failure(mock_get_provider):
    """If LLM throws, counts must not leak stale state."""
    from agent.nodes.requirements import understand_requirements

    mock_provider = MagicMock()
    mock_provider.call_detailed.side_effect = RuntimeError("api down")
    mock_get_provider.return_value = mock_provider

    result = understand_requirements(_base_state())

    assert result["module_count_max"] is None
    assert result["field_count_max"] is None
    assert result["project_name"] == "管理系统"


# ----- generate_modules -----

@patch("agent.nodes.generation.get_provider")
def test_generate_modules_uses_explicit_module_max_in_prompt(mock_get_provider):
    from agent.nodes.generation import generate_modules

    mock_provider = MagicMock()
    mock_provider.call_detailed.return_value = {
        "content": '[{"name":"A","label":"甲","description":"x"}]',
        "thinking": None, "prompt": "", "model": "x", "usage": None, "duration_ms": 0,
    }
    mock_get_provider.return_value = mock_provider

    state = _base_state("不超过 4 个模块")
    state["project_name"] = "X"
    state["business_domain"] = "X"
    state["module_count_max"] = 4

    generate_modules(state)

    sent_prompt = mock_provider.call_detailed.call_args.kwargs["prompt"]
    assert "AT MOST 4 modules" in sent_prompt
    assert "never exceed 4" in sent_prompt
    # User input is in the prompt so the LLM has the original phrasing
    assert "不超过 4 个模块" in sent_prompt


@patch("agent.nodes.generation.get_provider")
def test_generate_modules_falls_back_to_default_when_unspecified(mock_get_provider):
    from agent.nodes.generation import generate_modules

    mock_provider = MagicMock()
    mock_provider.call_detailed.return_value = {
        "content": '[{"name":"A","label":"甲","description":"x"}]',
        "thinking": None, "prompt": "", "model": "x", "usage": None, "duration_ms": 0,
    }
    mock_get_provider.return_value = mock_provider

    state = _base_state("生成系统")
    state["project_name"] = "X"
    state["business_domain"] = "X"
    state["module_count_max"] = None  # user didn't specify

    generate_modules(state)

    sent_prompt = mock_provider.call_detailed.call_args.kwargs["prompt"]
    assert "AT MOST 6 modules" in sent_prompt


# ----- generate_fields -----

@patch("agent.nodes.generation.get_provider")
def test_generate_fields_uses_explicit_field_max_in_prompt(mock_get_provider):
    from agent.nodes.generation import generate_fields

    mock_provider = MagicMock()
    mock_provider.call_detailed.return_value = {
        "content": '{"fields":[{"name":"a","label":"甲","type":"String","canSearch":true,"required":true,"description":"x"}]}',
        "thinking": None, "prompt": "", "model": "x", "usage": None, "duration_ms": 0,
    }
    mock_get_provider.return_value = mock_provider

    state = _base_state("每个模块不超过 12 个字段")
    state["modules"] = [{"name": "BookManagement", "label": "图书", "description": "..."}]
    state["field_count_max"] = 12

    generate_fields(state)

    sent_prompt = mock_provider.call_detailed.call_args.kwargs["prompt"]
    assert "AT MOST 12 fields" in sent_prompt
    assert "每个模块不超过 12 个字段" in sent_prompt


@patch("agent.nodes.generation.get_provider")
def test_generate_fields_falls_back_to_default_when_unspecified(mock_get_provider):
    from agent.nodes.generation import generate_fields

    mock_provider = MagicMock()
    mock_provider.call_detailed.return_value = {
        "content": '{"fields":[{"name":"a","label":"甲","type":"String","canSearch":true,"required":true,"description":"x"}]}',
        "thinking": None, "prompt": "", "model": "x", "usage": None, "duration_ms": 0,
    }
    mock_get_provider.return_value = mock_provider

    state = _base_state()
    state["modules"] = [{"name": "BookManagement", "label": "图书", "description": "..."}]
    state["field_count_max"] = None

    generate_fields(state)

    sent_prompt = mock_provider.call_detailed.call_args.kwargs["prompt"]
    assert "AT MOST 15 fields" in sent_prompt
